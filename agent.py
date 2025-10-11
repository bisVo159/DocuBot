from typing import Literal, Optional, Any
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from prompt_library.prompts import system_prompt, query_classifier_prompt
from utils.llms import LLMModel
from langgraph.checkpoint.memory import MemorySaver
from toolkit.tools import *

memory = MemorySaver()

class Router(BaseModel):
    next: Literal["information_node", "booking_node", "FINISH"] = Field(...,
        description=(
            "Determines which specialized worker to activate next in the workflow sequence: "
            "'information_node' when the user requests FAQs or doctor availability, "
            "'booking_node' when the user wants to book, reschedule, or cancel an appointment, "
            "'FINISH' when the user's query is fully resolved and no further action is required."
        )
    )
    reasoning: str = Field(...,
        description=(
            "Detailed justification for the routing decision, explaining the rationale but in short "
            "behind selecting the particular worker and how this advances the task toward resolution."
        )
    )

class query_classifierRoute(BaseModel):
    next_node: Literal["supervisor_node", "end"] = Field(
        ..., description="Determines the next node in the agent flow"
    )
    answer: Optional[str] = Field(
        None,
        description="Only filled if next_node is 'end'. Contains the assistant's reply to the user"
    )
    rephrased_query: Optional[str] = Field(
        None,
        description="Only filled if next_node is 'supervisor_node'. Contains the rewritten standalone query. Include patient_id if required"
    )

class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    query: str
    patient_id: int
    rephrased_query: str
    current_reasoning: str

class DoctorAppointmentAgent:
    def __init__(self):
        llm_model = LLMModel()
        self.gemini_model=llm_model.get_gemini_model()
        self.gemini_model_latest=llm_model.get_gemini_model_latest()
        self.groq_model=llm_model.get_groq_model()

    def query_classifier(self,state: AgentState) -> Command[Literal['supervisor','__end__']]:
        message_history = state['messages']
        user_query = state['query']
        patient_id = state['patient_id']

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", query_classifier_prompt),
                ("placeholder", "{messages}"),   
                ("human", "User query: {user_query}"),
                ("human", "patient_id: {patient_id}"),
            ]
        )

        chain= prompt | self.gemini_model.with_structured_output(query_classifierRoute)
        result:query_classifierRoute= chain.invoke({
            "messages": message_history,
            "user_query": user_query,
            "patient_id": patient_id
        })

        if result.next_node == "end":
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=user_query, name="query_classifier_node"),
                        AIMessage(content=result.answer, name="query_classifier_node")
                    ],
                    "current_reasoning": f"Routed to end because: {result.answer}",
                },
                goto="__end__",
            )
        else:
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=result.rephrased_query, name="query_classifier_node")
                    ],
                    "rephrased_query": result.rephrased_query,
                    "current_reasoning": f"Routed to supervisor_node because: {result.rephrased_query}",
                },
                goto="supervisor",
            )
    

    def supervisor_node(self, state:AgentState) -> Command[Literal['information_node', 'booking_node', '__end__']]:
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        
        last_msg = state['messages'][-1] if state["messages"] else None
        query = getattr(last_msg, "content", "nothing") if last_msg else ""
        
        if not query:
            return Command(goto='__end__', update={'current_reasoning': "No user query found."})
        
        response = self.gemini_model.with_structured_output(Router).invoke(messages)
        
        goto = response.next
            
        if goto == "FINISH":
            goto = END
        
        return Command(goto=goto, 
                    update={
            'current_reasoning': response.reasoning
            })

    def information_node(self,state:AgentState) -> Command[Literal['__end__']]:
        system_prompt = "You are specialized agent to provide information related to availability of doctors or any FAQs related to hospital based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n For your information."

        system_prompt = ChatPromptTemplate(
                [
                    (
                        "system",
                        system_prompt
                    ),
                    (
                        "placeholder", 
                        "{messages}"
                    )
                ]
            )

        information_agent = create_react_agent(
            model=self.gemini_model_latest,
            tools=[check_availability_by_doctor,check_availability_by_specialization] ,
            prompt=system_prompt)
        
        result = information_agent.invoke(state)
        
        return Command(
            update={
                "messages": result["messages"][-1]
            },
            goto="__end__"
        )
    
    def booking_node(self,state:AgentState) ->  Command[Literal['__end__']]:
        
        system_prompt = "You are specialized agent to set, cancel or reschedule appointment based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n For your information."
        
        system_prompt = ChatPromptTemplate(
                [
                    (
                        "system",
                        system_prompt
                    ),
                    (
                        "placeholder", 
                        "{messages}"
                    )
                ]
            )
        booking_agent = create_react_agent(
            model=self.gemini_model_latest,
            tools=[book_appointment,cancel_appointment,reschedule_appointment],
            prompt=system_prompt)
        

        result = booking_agent.invoke(state)
        
        return Command(
            update={
                "messages": result["messages"][-1]
            },
            goto="__end__"
        )
    
    def workflow(self):
        self.graph = StateGraph(AgentState)
        self.graph.add_node("query_classifier", self.query_classifier)
        self.graph.add_node("supervisor", self.supervisor_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)
        self.graph.add_edge(START, "query_classifier")
        self.app = self.graph.compile(checkpointer=memory)
        return self.app
