"""Domain exceptions for the conversation bounded context (Track B, P2-3 phase-2).

These errors signal INVARIANT violations at the domain level — the
application/infrastructure layers translate them to API status codes
(typically 409 for duplicate state, 422 for malformed request, 403 for
permission).
"""


class ConversationDomainError(Exception):
    """Base class for conversation domain errors."""


class ParticipantAlreadyPresentError(ConversationDomainError):
    """Attempted to add an agent that is already a participant."""


class ParticipantNotPresentError(ConversationDomainError):
    """Attempted to reference an agent that is not on the roster
    (remove, coordinator/focused assignment, or send-as)."""


class ParticipantLimitError(ConversationDomainError):
    """Operation would violate a mode-specific participant limit
    (e.g. adding a second agent to a SINGLE_AGENT conversation)."""


class CoordinatorRequiredError(ConversationDomainError):
    """AUTONOMOUS mode requires a coordinator_agent_id."""


class SenderNotInRosterError(ConversationDomainError):
    """A message's sender_agent_id is not in the conversation roster.

    This is the write-path invariant enforcing the Agent First / IM-group-chat
    rule: you cannot post as an agent you are not a participant-of.
    """


class MentionsInvalidError(ConversationDomainError):
    """One or more structured mentions reference agents not in the roster,
    or include the sender itself."""
