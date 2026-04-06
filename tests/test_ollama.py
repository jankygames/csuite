from langchain_ollama import OllamaLLM
 
llm = OllamaLLM(model='gpt-oss:20b')
response = llm.invoke('Reply with only the words: connection confirmed')
print(response)
