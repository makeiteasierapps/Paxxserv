import tiktoken

def token_counter(message):
    """Return the number of tokens in a string."""
    try:
        encoding = tiktoken.encoding_for_model("cl100k_base")
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    
    tokens_per_message = 3
    num_tokens = 0
    num_tokens += tokens_per_message
    num_tokens += len(encoding.encode(message))
    num_tokens += 3  # every reply is primed with <|im_start|>assistant<|im_sep|>
    return num_tokens