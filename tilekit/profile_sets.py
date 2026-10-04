"""
TileKit profile-set helpers.

Profiles are reusable behaviour packs for tile kinds. They let an app say:

- this kind accepts these source kinds;
- these relation/fallback rules handle interactions;
- these actions belong with the app/profile set.

The low-level rule engine stays renderer-neutral. Profile sets are a cleaner
composition layer for apps that want rich tile behaviour without stuffing all
registration logic into one plugin file.
"""

from .rules import InteractionProfile


class ProfileSet:
    """A named bundle of interaction profiles and optional actions."""

    def __init__(self, name="", profiles=None, actions=None, policies=None, cards=None):
        self.name = str(name or "")
        self.profiles = list(profiles or [])
        self.actions = list(actions or [])

        # Size policy per kind. A kind that ships rules should also be able
        # to say how it wants to be sized, rather than leaving every tile at
        # one cell and shrinking its font to fit.
        self.policies = dict(policies or {})
        self.cards = dict(cards or {})

    def add_card(self, kind, definition):
        """Attach an editor to a kind alongside its rules and sizing policy."""
        self.cards[str(kind)] = definition
        return self

    def add_policy(self, kind, policy):
        """Attach a SizePolicy to a kind and return self."""
        if kind and policy is not None:
            self.policies[str(kind)] = policy
        return self

    def policy_for(self, kind):
        """Return the SizePolicy for kind, or None."""
        return self.policies.get(str(kind or ""))

    def add_profile(self, profile):
        """Add an InteractionProfile to this set and return self."""
        if profile is not None:
            self.profiles.append(profile)
        return self

    def add_action(self, action):
        """Add an action instance to this set and return self."""
        if action is not None:
            self.actions.append(action)
        return self

    def profile(self, kind, accepts=None, relation_rules=None,
                fallback_rule=None, actions=None, overlap=None):
        """Build, add, and return an InteractionProfile."""
        built = profile(
            kind=kind,
            accepts=accepts,
            relation_rules=relation_rules,
            fallback_rule=fallback_rule,
            actions=actions,
            overlap=overlap,
        )
        self.add_profile(built)
        return built

    def install(self, board):
        """Register all profiles/actions onto a board and return the board."""
        if board is None:
            return None

        registry = getattr(getattr(board, "rule_engine", None), "registry", None)
        if registry is not None:
            for item in self.profiles:
                registry.register(item)

        action_registry = getattr(board, "action_registry", None)
        if action_registry is not None:
            for action in self.actions:
                action_registry.register(action)

        for kind, policy in self.policies.items():
            board.set_size_policy(kind, policy)
        for kind, definition in self.cards.items():
            board.set_card(kind, definition)

        return board


def profile(kind, accepts=None, relation_rules=None,
            fallback_rule=None, actions=None, overlap=None):
    """Create a compact InteractionProfile.

    overlap is a convenience for the common TileKit pattern where overlap and
    fallback use the same rule.
    """
    rules = dict(relation_rules or {})

    if overlap is not None:
        rules.setdefault("overlap", overlap)
        if fallback_rule is None:
            fallback_rule = overlap

    return InteractionProfile(
        kind=kind,
        accepts=accepts,
        relation_rules=rules,
        fallback_rule=fallback_rule,
        actions=actions,
    )


def install_profile_set(board, profile_set):
    """Install a ProfileSet-like object onto a board."""
    if profile_set is None:
        return board

    if hasattr(profile_set, "install"):
        return profile_set.install(board)

    for item in list(profile_set or []):
        registry = getattr(getattr(board, "rule_engine", None), "registry", None)
        if registry is not None:
            registry.register(item)

    return board