from ...compiler.helpers import Location


class QueryStateManager:
    class StateTransitionError(Exception):
        pass

    class QueryState:
        """
        Manages the state of a query as IR blocks are traversed. This includes location most
        importantly, and whether a location is in an optional, recursive, or fold context. This state
        can then be passed along and shared with other blocks, that logically have the same state (
        a Selection and Relation at the same location, as an example).
        """

        def __init__(self, location, in_optional, in_fold, is_recursive, location_types):
            self.location = location
            self.in_optional = in_optional
            self.in_fold = in_fold
            self.is_recursive = is_recursive
            self.location_types = location_types

        def current_type(self):
            return self.location_types[self.location].name

        @property
        def current_vertex(self):
            return self.location.query_path[-1]

        def outer_type(self):
            if len(self.location.query_path) < 2:
                return None
            outer_location = Location(self.location.query_path[:-1])
            return self.location_types[outer_location].name

        def get_location(self):
            return self.location

    def __init__(self, location_types):
        self.query_path = []
        self.in_optional = False
        self.in_fold = False
        self.is_recursive = False
        self.location_to_state = {}
        self.recursive_locations = set()
        self.latest_snapshot = None
        self.location_types = location_types
        self.optional_id = 0
        self.recursive_count = 0

    def snapshot_state(self):
        current_location = Location(tuple(self.query_path))
        if current_location in self.location_to_state:
            raise QueryStateManager.StateTransitionError(
                'Snapshot for location {} already exists.'.format(current_location)
            )
        self.location_to_state[current_location] = QueryStateManager.QueryState(
            location=current_location,
            in_optional=self.in_optional,
            in_fold=self.in_fold,
            is_recursive=self.is_recursive,
            location_types=self.location_types,
        )
        self.latest_snapshot = self.location_to_state[current_location]

    def state_for_path(self, query_path):
        return self.location_to_state[Location(query_path)]

    def get_state(self):
        if self.latest_snapshot is None:
            raise QueryStateManager.StateTransitionError('QueryStateManager has no snapshots.')
        return self.latest_snapshot

    def enable_state(self, state_name):
        current_state = self.safe_get_state(state_name)
        if current_state:
            raise QueryStateManager.StateTransitionError(
                'Invalid state transition, state "{}" is already enabled.'
            )
        setattr(self, state_name, True)

    def disable_state(self, state_name):
        current_state = self.safe_get_state(state_name)
        if not current_state:
            raise QueryStateManager.StateTransitionError(
                'Invalid state transition, state "{}" is already disabled.'
            )
        setattr(self, state_name, False)

    def safe_get_state(self, state_name):
        if not hasattr(self, state_name):
            raise QueryStateManager.StateTransitionError(
                'QueryStateManager has no state "{}"'.format(state_name)
            )
        current_state = getattr(self, state_name)
        return current_state

    def enter_fold(self):
        self.enable_state('in_fold')

    def exit_fold(self):
        self.disable_state('in_fold')

    def enter_optional(self):
        self.enable_state('in_optional')

    def exit_optional(self):
        self.disable_state('in_optional')
        self.optional_id += 1

    def enter_recursive(self):
        self.enable_state('is_recursive')

    def exit_recursive(self):
        self.disable_state('is_recursive')

    def enter_type(self, location):
        self.query_path.append(location)
        self.snapshot_state()

    def exit_type(self):
        if len(self.query_path) == 0:
            raise QueryStateManager.StateTransitionError('No type to exit from.')
        self.query_path.pop()