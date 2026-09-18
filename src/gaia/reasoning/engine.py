class LLMAdapter:
    """Base interface / stub for LLM reasoning engines."""

    def __init__(self, provider="stub", api_key=None):
        self.provider = provider
        self.api_key = api_key

    def generate_response(self, prompt, system_prompt=None):
        """Generates a text response from the model or a fallback response if offline."""
        if self.provider == "stub":
            return f"[LLM Stub Response]: Processed prompt - '{prompt}'"
        return f"[{self.provider} Output]: Response generated."


class ReasoningEngine:
    """Handles agent cognitive reasoning, prompt construction, and LLM query delegation."""

    def __init__(self, adapter=None):
        self.adapter = adapter or LLMAdapter(provider="stub")

    def generate_dialogue(self, speaker, listener, topic=None):
        """Generates contextual dialogue between two citizens."""
        prompt = f"Citizen {speaker.name} speaks to {listener.name}"
        if topic:
            prompt += f" about {topic}"
        
        system_prompt = "You are an AI generating realistic simulation dialogue between citizens."
        return self.adapter.generate_response(prompt, system_prompt=system_prompt)

    def formulate_plan(self, citizen, goal):
        """Generates a high-level step-by-step plan for a citizen's goal."""
        prompt = f"Formulate a plan for citizen {citizen.name} to achieve goal: {goal}"
        return self.adapter.generate_response(prompt)
