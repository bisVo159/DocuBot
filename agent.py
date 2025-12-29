from typing import Literal, Optional, Any
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.graph import START, StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import ToolNode, tools_condition
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

class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    query: str
    current_reasoning: str

class DoctorAppointmentAgent:
    def __init__(self):
        llm_model = LLMModel()
        self.gemini_model=llm_model.get_gemini_model()
        self.gemini_model_latest=llm_model.get_gemini_model_latest()
        self.groq_model=llm_model.get_groq_model()

        self.info_tools = [check_availability_by_doctor, check_availability_by_specialization, get_available_doctors, get_available_specializations, get_available_doctors_on_date]
        self.booking_tools = [book_appointment, cancel_appointment, reschedule_appointment]

    def query_classifier(self,state: AgentState) -> Command[Literal['supervisor','__end__']]:
        user_query = state['query']

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", query_classifier_prompt),
                ("human", "User query: {user_query}")
            ]
        )

        chain= prompt | self.gemini_model_latest.with_structured_output(query_classifierRoute)
        result:query_classifierRoute= chain.invoke({
            "user_query": user_query
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
                        HumanMessage(content=user_query, name="query_classifier_node")
                    ],
                    "current_reasoning": f"Routed to supervisor_node because: {user_query}",
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
        
        response = self.gemini_model_latest.with_structured_output(Router).invoke(messages)
        
        goto = response.next
            
        if goto == "FINISH":
            goto = END
        
        return Command(goto=goto, 
                    update={
            'current_reasoning': response.reasoning
            })

    def information_node(self,state:AgentState):
        system_text = "You are specialized agent to provide information related to availability of doctors or any FAQs related to hospital based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n For your information."

        model_with_tools = self.gemini_model_latest.bind_tools(self.info_tools)
        messages = [SystemMessage(content=system_text)] + state["messages"]
        response = model_with_tools.invoke(messages)

        return {"messages": [response]}
    
    def booking_node(self,state:AgentState):
        
        system_text = "You are specialized agent to set, cancel or reschedule appointment based on the query. You have access to the tool.\n Make sure to ask user politely if you need any further information to execute the tool.\n For your information."
        
        model_with_tools = self.gemini_model_latest.bind_tools(self.booking_tools)
        messages = [SystemMessage(content=system_text)] + state["messages"]
        response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    def workflow(self):
        self.graph = StateGraph(AgentState)
        self.graph.add_node("query_classifier", self.query_classifier)
        self.graph.add_node("supervisor", self.supervisor_node)
        self.graph.add_node("information_node", self.information_node)
        self.graph.add_node("booking_node", self.booking_node)

        self.graph.add_node("tools", ToolNode(self.info_tools + self.booking_tools))
        self.graph.add_edge(START, "query_classifier")
        self.graph.add_conditional_edges(
            "information_node",
            tools_condition, 
        )
        self.graph.add_conditional_edges(
            "booking_node",
            tools_condition, 
        )
        def route_after_tool(state):
            last_msg = state['messages'][-1]
            if last_msg.name in [t.name for t in self.info_tools]:
                return "information_node"
            return "booking_node"
        self.graph.add_conditional_edges("tools", route_after_tool)
        self.app = self.graph.compile(checkpointer=memory)
        return self.app
