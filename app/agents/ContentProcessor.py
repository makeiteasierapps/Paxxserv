import dspy
import os
from dspy import Signature, InputField, OutputField
from dspy.functional import TypedPredictor
from pydantic import BaseModel
from typing import List

class ActionItemsOutput(BaseModel):
    actions: List[str]

class ActionItemsSignature(Signature):
    """
    From the content, extract the suggested action items.
    """
    content = InputField()
    actions: ActionItemsOutput = OutputField(desc='Suggested actions should come directly from the content. If no actions are required, the output should be an empty list.')

class NewActionItemsSignature(Signature):
    """
    Create a new list of action items by combining two lists.
    """
    list_1 = InputField()
    list_2 = InputField()
    combined_list: ActionItemsOutput = OutputField()

class DocumentContent(Signature):
    """From the content, extract the title and summary of the document.
    """
    document = InputField()
    title = OutputField(desc='Short descriptive title of the document')
    summary = OutputField()

class ContentProcessor:
    def __init__(self, model):
        self.model = model
        self.openai_key = os.getenv('OPENAI_API_KEY')
        
        try:
            lm = dspy.OpenAI(model=self.model, api_key=self.openai_key)
            dspy.settings.configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")

    def extract_content(self, moment):
        content = moment['transcript']
        extract_actions = TypedPredictor(ActionItemsSignature)
        actions_pred = extract_actions(content=content)
        generate_summary_prompt = dspy.ChainOfThought(DocumentContent)
        content_pred = generate_summary_prompt(document=content)

        extracted_content = {
            'title': content_pred.title,
            'summary': content_pred.summary,
            'actionItems': actions_pred.actions.actions
        }
        return extracted_content

    def diff_snapshots(self, previous_snapshot, current_snapshot):
        # Takes the summary of the previous snapshot, combines it with the summary of the current snapshot, and generates a new summary.
        generate_new_summary_prompt = dspy.ChainOfThought('summary_1, summary_2 -> new_summary')
        new_summary_pred = generate_new_summary_prompt(summary_1=previous_snapshot['summary'], summary_2=current_snapshot['summary'])
        new_summary = new_summary_pred.new_summary

        # Takes the action items of the previous snapshot, combines it with the action items of the current snapshot, and generates a new list of action items.
        list_1_str = ', '.join(previous_snapshot['actionItems'])
        list_2_str = ', '.join(current_snapshot['actionItems'])
        generate_new_actions_prompt = TypedPredictor(NewActionItemsSignature)
        new_action_items_pred = generate_new_actions_prompt(list_1=list_1_str, list_2=list_2_str)
        new_action_items = new_action_items_pred.combined_list.actions

        # Takes the title of the previous snapshot, combines it with the title of the current snapshot, and generates a new title.
        generate_new_title_prompt = dspy.ChainOfThought('title_1, title_2 -> new_title')
        new_title_pred = generate_new_title_prompt(title_1=previous_snapshot['title'], title_2=current_snapshot['title'])
        new_title = new_title_pred.new_title

        new_snapshot = {
            'title': new_title,
            'summary': new_summary,
            'actionItems': new_action_items
        }
        return new_snapshot