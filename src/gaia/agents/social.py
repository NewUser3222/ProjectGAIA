class SocialInteraction:
    """Handles social interactions and mutual state updates between citizens."""
    
    SUPPORTED_TYPES = ["talk", "share", "dispute"]

    def __init__(self, interaction_type, initiator, target):
        if interaction_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported interaction type: {interaction_type}")
        if not initiator or not target:
            raise ValueError("Initiator and target must be valid citizens.")
        if getattr(initiator, "citizen_id", None) == getattr(target, "citizen_id", None):
            raise ValueError("A citizen cannot initiate a social interaction with themselves.")

        self.interaction_type = interaction_type
        self.initiator = initiator
        self.target = target

    def execute(self, current_tick=0):
        """Executes the social action and updates mutual relationships and memories."""
        if self.interaction_type == "talk":
            return self._handle_talk(current_tick)
        elif self.interaction_type == "share":
            return self._handle_share(current_tick)
        elif self.interaction_type == "dispute":
            return self._handle_dispute(current_tick)

    def _handle_talk(self, tick):
        self._update_relationship(self.initiator, self.target, trust_delta=2, affinity_delta=3)
        self._update_relationship(self.target, self.initiator, trust_delta=2, affinity_delta=3)

        self._record_memory(self.initiator, f"Had a friendly conversation with {self.target.name}", tick)
        self._record_memory(self.target, f"Had a friendly conversation with {self.initiator.name}", tick)

        return {
            "success": True,
            "type": "talk",
            "message": f"{self.initiator.name} talked with {self.target.name}."
        }

    def _handle_share(self, tick):
        self._update_relationship(self.initiator, self.target, trust_delta=5, affinity_delta=4)
        self._update_relationship(self.target, self.initiator, trust_delta=8, affinity_delta=5)

        self._record_memory(self.initiator, f"Shared resources with {self.target.name}", tick)
        self._record_memory(self.target, f"{self.initiator.name} shared resources with me", tick)

        return {
            "success": True,
            "type": "share",
            "message": f"{self.initiator.name} shared resources with {self.target.name}."
        }

    def _handle_dispute(self, tick):
        self._update_relationship(self.initiator, self.target, trust_delta=-10, affinity_delta=-15)
        self._update_relationship(self.target, self.initiator, trust_delta=-12, affinity_delta=-15)

        self._record_memory(self.initiator, f"Got into a dispute with {self.target.name}", tick)
        self._record_memory(self.target, f"Had an argument with {self.initiator.name}", tick)

        return {
            "success": True,
            "type": "dispute",
            "message": f"{self.initiator.name} had a dispute with {self.target.name}."
        }

    def _update_relationship(self, subject, object_citizen, trust_delta, affinity_delta):
        # Attempt to locate existing relationship
        rel = None
        if hasattr(subject, "get_relationship"):
            rel = subject.get_relationship(object_citizen.citizen_id)
        elif hasattr(subject, "relationships"):
            rels = subject.relationships
            if hasattr(rels, "get_relationship"):
                rel = rels.get_relationship(object_citizen.citizen_id)
            elif isinstance(rels, dict):
                rel = rels.get(object_citizen.citizen_id)

        # If relationship doesn't exist, create it safely
        if not rel and hasattr(subject, "add_relationship"):
            try:
                subject.add_relationship(object_citizen.citizen_id, object_citizen.name)
            except ValueError:
                pass
            
            if hasattr(subject, "get_relationship"):
                rel = subject.get_relationship(object_citizen.citizen_id)

        # Update relationship metrics
        if rel:
            if hasattr(rel, "trust"):
                rel.trust = max(0, min(100, rel.trust + trust_delta))
            if hasattr(rel, "affinity"):
                rel.affinity = max(-100, min(100, rel.affinity + affinity_delta))

    def _record_memory(self, citizen, text, tick):
        if hasattr(citizen, "add_memory"):
            citizen.add_memory(text, tick)
