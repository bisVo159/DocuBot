from typing import Literal, List, Any
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from prompt_library.prompts import system_prompt,information_node_template, booking_node_template
from utils.llms import LLMModel
from langchain.prompts import PromptTemplate
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

class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    patient_id: int
    query: str
    rephrased_query: str
    current_reasoning: str

class DoctorAppointmentAgent:
    def __init__(self):
        llm_model = LLMModel()
        self.gemini_model=llm_model.get_gemini_model()
        self.groq_model=llm_model.get_groq_model()

    def query_rewriter(self, state: AgentState) -> Command[Literal['supervisor']]:
        message_history = state['messages']
        user_query = state['query']
        patient_id = state['patient_id']
        query_rewriter_prompt = """
        You are a helpful assistant that rephrases the user's question to be a standalone question
        You will receive:
        - patient_id
        - conversation history
        - the latest user query

        Rephrase the user query into a clearer and more meaningful version. 
        Always include the patient_id in the rewritten query.
        """

        query_rewriter_prompt = ChatPromptTemplate(
            [
                ("system", query_rewriter_prompt),
                ("placeholder", "{messages}"),   
                ("human", "User query: {user_query}"),
                ("human", "patient_id: {patient_id}"),
            ]
        )

        chain= query_rewriter_prompt | self.gemini_model
        result= chain.invoke({
            "messages": message_history,
            "user_query": user_query,
            "patient_id": patient_id
        })
        
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result.content, name="query_rewriter_node")
                ],
                "rephrased_query": result.content,
            },
            goto="supervisor",
        )
    
    def supervisor_node(self, state:AgentState) -> Command[Literal['information_node', 'booking_node', '__end__']]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"user's identification number is {state['patient_id']}"},
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
            'current_reasoning': response.reasoning, 
            'messages': [AIMessage(content=response.reasoning, name="supervisor_node")]
            })

    def information_node(self,state:AgentState) -> Command[Literal['supervisor']]:
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
            model=self.gemini_model,
            tools=[check_availability_by_doctor,check_availability_by_specialization] ,
            prompt=system_prompt)
        
        result = information_agent.invoke(state)
        
        return Command(
            update={
                "messages": result["messages"]
            },
            goto="supervisor"
        )
    
    def booking_node(self,state:AgentState) ->  Command[Literal['supervisor']]:
        
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
            model=self.gemini_model,
            tools=[book_appointment,cancel_appointment,reschedule_appointment],
            prompt=system_prompt)
        

        result = booking_agent.invoke(state)
        
        return Command(
            update={
                "messages": result["messages"]
            },
            goto="supervisor"
        )
    
    def workflow(self):
        self.graph = StateGraph(AgentState)
        self.graph.add_node("query_rewriter", self.query_rewriter)
        self.graph.add_node("supervisor", self.supervisor_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)
        self.graph.add_edge(START, "query_rewriter")
        self.app = self.graph.compile(checkpointer=memory)
        return self.app
