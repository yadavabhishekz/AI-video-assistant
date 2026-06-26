from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

import os

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3
    )

def split_transcribe(transcript : str) ->list:
    splitter = RecursiveCharacterTextSplitter(
    chunk_size=4000,
    chunk_overlap=400
    )

    return splitter.split_text(transcript)

def summarize(transcript : str) ->  str:
    llm = get_llm()

    map_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Summarize this postion fo a meeting transcript concisely."),
            ("human", "{text}")
        ]
    )

    map_chain = map_prompt | llm | StrOutputParser()

    chunks = split_transcribe(transcript)

    chunk_summaries = [map_chain.invoke({"text" : chunk}) for chunk in chunks]

    combined = "\n\n".join(chunk_summaries)

    combined_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", 
             "You are an expert meetings summarizer. Combine these partial summaries into one final professional meeting summary in bullet points."),
            ("human", "{text}")
        ]
    )

    combined_chain = (
        RunnablePassthrough() 
        | RunnableLambda(lambda x:{"text" : x}) 
        | combined_prompt 
        | llm 
        | StrOutputParser()
    )

    return combined_chain.invoke(combined)


def generate_title(transcript : str) -> str:
     llm = get_llm()
     title_prompt = ChatPromptTemplate.from_messages(
         [
             ("system", "Based on the meething transcript, generate a short professionl meeting title(max 8 words). Only return the title, nothing else."),
             ("human", "{text}")
         ]
     )

     title_chain = (
         RunnablePassthrough() 
         | RunnableLambda(lambda x:{"text" : x}) 
         | title_prompt 
         | llm 
         | StrOutputParser()
     )

     return title_chain.invoke(transcript[:3000])
