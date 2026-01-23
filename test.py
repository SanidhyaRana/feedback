import os
from agents import Agent, Runner
from dotenv import load_dotenv  
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("api_key")

weather_agent = Agent(
    name="Weather Agent",
    instructions=(
        "You are a weather expert. Provide fake weather updates. "
        "If the user asks about stocks, movies, or general chat, "
        "handoff control back to the Orchestrator."
    )
)

stock_agent = Agent(
    name="Stock Agent",
    instructions=(
        "You are a stock market analyst. Provide fake stock prices. "
        "If the user asks about weather, movies, or chat, "
        "handoff control back to the Orchestrator."
    )
)

movie_agent = Agent(
    name="Movie Agent",
    instructions=(
        "You are a movie critic. Recommend movies. "
        "If the user asks about other topics, handoff to the Orchestrator."
    )
)

chat_agent = Agent(
    name="Conversation Agent",
    instructions=(
        "You are a friendly assistant for small talk. "
        "If the user asks for specific data (weather, stock, movies), "
        "handoff to the Orchestrator."
    )
)

orchestrator = Agent(
    name="Orchestrator",
    instructions=(
        "You are the central router. Your only job is to classify the user's intent "
        "and handoff to the correct specialist agent. "
        "Do not answer the user's question directly."
    ),
    handoffs=[weather_agent, stock_agent, movie_agent, chat_agent]
)


weather_agent.handoffs = [orchestrator]
stock_agent.handoffs = [orchestrator]
movie_agent.handoffs = [orchestrator]
chat_agent.handoffs = [orchestrator]


def main():
    print("Try asking about weather, then switch to stocks immediately.")
    
    current_agent = orchestrator
    
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        
        
        result = Runner.run_sync(
            starting_agent=current_agent,
            input=user_input
        )
        
        print(f"{result.final_output}")
        

if __name__ == "__main__":
    main()
