"""
TileKit interaction controller.

This is the first extraction of touch/drag/drop behaviour out of UIBoardView.
It deliberately preserves the current simple behaviour before importing more
advanced Tile Calc concepts.
"""

import math


class InteractionController:
    """Small board interaction state machine used by UI layers."""

    def __init__(self, board_view):
        self.view = board_view
        self.mode = "idle"
        self.drag_obj = None
        self.drag_offset = (0, 0)
        self.drag_start_position = None
        self.hover_target = None
        self.last_action_origin = None
        self.start_point = None
        self.tap_move_threshold = 6.0

        # Live merge intent. This ports the important old Tile Calc "birch"
        # behaviour: direction is learned from how the drag enters a target
        # radius, can update during the drag, and starts near a target are
        # skipped until the drag exits/re-enters.
        self.merge_entry_radius_mult = 1.0
        self.merge_search_radius_mult = 2.0
        self.merge_release_radius_mult = 1.35
        self._intent_direction = None
        self._intent_target_id = None
        self._intent_trail_prev = None
        self._intent_inside = False
        self._intent_skip_targets = set()
        self._drag_prev_position = None
        self._drag_last_position = None

        # A single finger on empty board space pans the workspace. Lasso
        # selection was removed: it competed with panning for the same gesture
        # and panning is the far more common intent. Group selection remains a
        # framework capability through Board.set_group_selection, so a future
        # explicit select tool can drive it without a default-gesture conflict.
        self.pan_last_point = None

        # First boring group-drag state. It reuses SelectionModel.group and
        # deliberately avoids group merge/drop semantics for now.
        self.group_drag_objects = []
        # Pointer start in logical/world coordinates. Screen-space start_point
        # remains separate because tap/pan thresholds are measured in pixels.
        self.pointer_start_position = None
        self.group_drag_start_positions = {}

    def reset_to_neutral(self, clear_selection=True, status="ready"):
        self._cancel_drag_history()
        view = self.view

        obj = self.drag_obj
        if obj is not None:
            try:
                obj.set_dragging(False)
                view.sync_object(obj)
            except Exception:
                pass

        for item in list(self.group_drag_objects):
            try:
                item.set_dragging(False)
                view.sync_object(item)
            except Exception:
                pass

        self.drag_obj = None
        self.drag_start_position = None
        self.drag_offset = (0, 0)
        self.hover_target = None
        self.last_action_origin = None
        self.start_point = None
        self.pointer_start_position = None
        self.pan_last_point = None
        self.group_drag_objects = []
        self.group_drag_start_positions = {}
        self._reset_live_merge_intent()
        self.mode = "idle"

        view.transient.reset(
            clear_selection=clear_selection,
            status=status,
        )

    def begin(self, event):
        view = self.view
        p = event.point
        world = event.position if event.position is not None else p
        obj = view.object_at_point(p)

        if obj is None:
            # Empty-space geometry remains screen-space because pan/tap
            # thresholds are visual pixel interactions.
            # Without a camera there is nothing to pan, so an empty-space touch
            # stays a plain tap that dismisses transient UI.
            self.reset_to_neutral(clear_selection=True, status="pan pending")
            self.start_point = p
            self.pointer_start_position = world
            self.pan_last_point = p
            self.mode = "pan_pending" if self._can_pan() else "idle"
            view.log_session_event("empty_touch_begin", point=p, mode=self.mode)
            return

        group = self._current_group()
        if len(group) > 1 and obj in group:
            self.drag_obj = obj
            self.drag_start_position = obj.position
            self.start_point = p
            self.pointer_start_position = world
            self.group_drag_objects = list(group)
            self.group_drag_start_positions = {}
            for item in self.group_drag_objects:
                self.group_drag_start_positions[id(item)] = tuple(
                    getattr(item, "position", None) or (0, 0)
                )

            ox, oy = obj.position or (0, 0)
            self.drag_offset = (world[0] - ox, world[1] - oy)

            view.transient.hide_action_dock()
            view.set_status("group tap pending {}".format(len(group)))
            view.log_session_event(
                "group_touch_begin",
                point=p,
                object_id=getattr(obj, "id", None),
                object_label=getattr(obj, "label", None),
                group_count=len(group),
            )
            self.mode = "group_tap_pending"
            return

        view.board.select(obj)
        view.transient.hide_action_dock()

        self.drag_obj = obj
        self.drag_start_position = obj.position
        self.start_point = p
        self.pointer_start_position = world
        self._reset_live_merge_intent(obj)

        ox, oy = obj.position or (0, 0)
        self.drag_offset = (world[0] - ox, world[1] - oy)

        view.set_status("tap pending {} {}".format(obj.kind, obj.label))
        view.log_session_event(
            "object_touch_begin",
            point=p,
            object_id=getattr(obj, "id", None),
            object_kind=getattr(obj, "kind", None),
            object_label=getattr(obj, "label", None),
        )
        self.mode = "tap_pending"

    def _viewport(self):
        """Return the board camera.

        The viewport belongs to the coordinate system, not the view, because
        it is what projects world coordinates onto the screen.
        """
        board = getattr(self.view, "board", None)
        coords = getattr(board, "coords", None)
        return getattr(coords, "viewport", None)

    def _can_pan(self):
        """Return True when the board has a pannable camera."""
        return self._viewport() is not None

    def _pan_viewport(self, point):
        """Move the camera by the screen delta since the last pan point."""
        viewport = self._viewport()
        if viewport is None:
            return

        last = self.pan_last_point or point
        viewport.pan_by((point[0] - last[0], point[1] - last[1]))
        self.pan_last_point = point

        notify = getattr(self.view, "_viewport_changed", None)
        if notify is not None:
            try:
                notify(viewport)
            except Exception:
                pass

    def _start_drag_history(self):
        """Capture the board before the first movement or dragging flag."""
        history = getattr(self.view.board, "history", None)
        self._drag_history_before = (
            history.snapshot() if history is not None else None
        )
        self._drag_history_label = "Move tiles"

    def _finish_drag_history(self):
        """Record one completed move/merge, ignoring selection-only changes."""
        before = getattr(self, "_drag_history_before", None)
        self._drag_history_before = None
        history = getattr(self.view.board, "history", None)
        if before is None or history is None:
            return

        def content(snapshot):
            return [
                {key: value for key, value in item.items() if key != "state"}
                for item in snapshot.get("objects", [])
            ]

        if content(before) != content(history.snapshot()):
            history.record_change(
                before, label=getattr(self, "_drag_history_label", "Move tiles")
            )

    def _cancel_drag_history(self):
        """Roll back interrupted movement without replacing object identities."""
        before = getattr(self, "_drag_history_before", None)
        self._drag_history_before = None
        if before is None:
            return
        positions = {
            item["data"]["id"]: item["position"]
            for item in before.get("objects", [])
        }
        for obj in self.view.board.objects:
            if obj.id in positions:
                obj.position = tuple(positions[obj.id])
                obj.set_dragging(False)
                self.view.sync_object(obj)

    def moved(self, event):
        view = self.view
        p = event.point
        world = event.position if event.position is not None else p

        if self.mode == "pan_pending":
            sx, sy = self.start_point or p
            dx = p[0] - sx
            dy = p[1] - sy
            if (dx * dx + dy * dy) ** 0.5 < self.tap_move_threshold:
                return

            self.mode = "pan"
            self.pan_last_point = self.start_point or p
            view.transient.clear_preview()
            view.log_session_event("pan_start", point=p)
            view.set_status("pan")

        if self.mode == "pan":
            self._pan_viewport(p)
            view.set_status("pan")
            return

        if self.mode == "group_tap_pending":
            sx, sy = self.start_point or p
            dx = p[0] - sx
            dy = p[1] - sy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < self.tap_move_threshold:
                return

            self._start_drag_history()
            self.mode = "group_drag"
            view.transient.clear_preview()
            view.transient.hide_action_dock()
            view.log_session_event(
                "group_drag_start",
                point=p,
                group_count=len(self.group_drag_objects),
            )
            for item in list(self.group_drag_objects):
                try:
                    item.set_dragging(True)
                    view.sync_object(item)
                except Exception:
                    pass

        if self.mode == "group_drag":
            start_world = self.pointer_start_position or world
            dx = world[0] - start_world[0]
            dy = world[1] - start_world[1]

            for item in list(self.group_drag_objects):
                start = self.group_drag_start_positions.get(id(item))
                if start is None:
                    continue
                item.position = (start[0] + dx, start[1] + dy)
                view.sync_object(item)

            view.transient.clear_preview()
            view.set_status("group drag {}".format(len(self.group_drag_objects)))
            return

        obj = self.drag_obj
        if obj is None:
            return

        if self.mode == "tap_pending":
            sx, sy = self.start_point or p
            dx = p[0] - sx
            dy = p[1] - sy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < self.tap_move_threshold:
                return

            self._start_drag_history()
            self.mode = "drag"
            obj.set_dragging(True)
            view.transient.hide_action_dock()
            view.log_session_event(
                "drag_start",
                point=p,
                object_id=getattr(obj, "id", None),
                object_kind=getattr(obj, "kind", None),
                object_label=getattr(obj, "label", None),
                start_position=self.drag_start_position,
            )

            renderer = getattr(obj, "renderer", None)
            view_obj = getattr(renderer, "view", None)
            if view_obj is not None:
                try:
                    view_obj.bring_to_front()
                except Exception:
                    pass

        if self.mode != "drag":
            return

        offx, offy = self.drag_offset
        prev_pos = getattr(obj, "position", None)
        obj.position = (world[0] - offx, world[1] - offy)
        self._drag_prev_position = prev_pos
        self._drag_last_position = obj.position
        view.sync_object(obj)

        nearby_for_intent = self._nearest_drop_target(
            obj,
            p,
            radius_mult=self.merge_search_radius_mult,
            require_rule=False,
        )
        if nearby_for_intent is not None:
            self._update_live_merge_intent(obj, nearby_for_intent)
        else:
            self._intent_trail_prev = obj.position
            self._intent_inside = False

        target = self._resolve_drop_target(obj, p, for_preview=True)
        if target is None:
            target = self._nearest_drop_target(obj, p)
        view._set_hover_target(target)

        if target is not None:
            relation = view.board.coords.relation(obj, target, {
                "drag_start_position": self.drag_start_position,
                "profile_position": self._profile_position_for_target(target),
            })
            preview = self.preview_interaction(obj, target, {
                "board": view.board,
                "drop_relation": relation,
            })
            view.transient.set_preview(preview)

            if preview is not None and getattr(preview, "label", None):
                view.set_status(
                    "preview={} target={} relation={}".format(
                        preview.label,
                        target.label,
                        relation.relation,
                    )
                )
            else:
                view.set_status(
                    "target={} relation={} dir={} dist={:.1f}".format(
                        target.label,
                        relation.relation,
                        relation.direction,
                        relation.distance or 0.0,
                    )
                )
        else:
            view.transient.clear_preview()
            view.set_status("drag {} {}".format(obj.kind, obj.label))

    def ended(self, event):
        view = self.view
        self.pointer_start_position = None

        if self.mode == "pan_pending":
            self.pan_last_point = None
            self.start_point = None
            self.mode = "idle"
            view.transient.reset(clear_selection=True, status="empty")
            view.log_session_event("empty_tap", point=event.point)
            return

        if self.mode == "pan":
            self.pan_last_point = None
            self.start_point = None
            self.mode = "idle"
            view.transient.clear_preview()
            view.log_session_event("pan_end", point=event.point)
            view.set_status("ready")
            return

        if self.mode == "group_tap_pending":
            count = len(self.group_drag_objects)
            self.drag_obj = None
            self.drag_start_position = None
            self.drag_offset = (0, 0)
            self.start_point = None
            self.group_drag_start_positions = {}
            self.mode = "idle"
            view.transient.clear_preview()
            view.transient.show_group_actions(origin=event.point)
            view.log_session_event("group_tap", point=event.point, group_count=count)
            view.set_status("group selected {}".format(count))
            return

        if self.mode == "group_drag":
            count = len(self.group_drag_objects)
            labels = [getattr(item, "label", None) for item in self.group_drag_objects]
            for item in list(self.group_drag_objects):
                try:
                    item.position = view.board.coords.snap(item.position, item)
                    item.set_dragging(False)
                    view.sync_object(item)
                except Exception:
                    pass

            self.drag_obj = None
            self.drag_start_position = None
            self.drag_offset = (0, 0)
            self.start_point = None
            self.group_drag_objects = []
            self.group_drag_start_positions = {}
            self.mode = "idle"
            view.transient.clear_preview()
            view.transient.show_group_actions(origin=event.point)
            view.log_session_event(
                "group_drop",
                point=event.point,
                group_count=count,
                labels=labels,
            )
            self._finish_drag_history()
            view.set_status("group dropped {}".format(count))
            return

        obj = self.drag_obj
        if obj is None:
            return

        if self.mode == "tap_pending":
            obj.set_dragging(False)
            view.sync_object(obj)
            self.drag_obj = None
            self.drag_start_position = None
            self.drag_offset = (0, 0)
            self.start_point = None
            self.mode = "idle"
            view._set_hover_target(None)
            view.transient.clear_preview()
            view._update_action_dock(origin=event.point)
            view.log_session_event(
                "object_tap",
                point=event.point,
                object_id=getattr(obj, "id", None),
                object_kind=getattr(obj, "kind", None),
                object_label=getattr(obj, "label", None),
            )
            view.set_status("selected {} {}".format(obj.kind, obj.label))
            return

        if self.mode != "drag":
            self.reset_to_neutral(clear_selection=False, status="ready")
            return

        # Resolve the target where the finger actually released the object.
        # Snapping an even-cell span shifts its centre by half a cell and can
        # move it outside a smaller target before hit testing has happened.
        release_position = obj.position
        obj.position = view.board.coords.snap(obj.position, obj)

        # Old Tile Calc lesson:
        # preview/intent may use nearby target radius, but release commit should
        # be stricter. A directional merge only commits when the released object
        # is actually on a target.
        target = view.object_at_point(
            view.board.coords.to_screen(release_position),
            excluding=obj,
        )

        source_was_removed = False

        if target is not None:
            relation = view.board.coords.relation(obj, target, {
                "drag_start_position": self.drag_start_position,
                "profile_position": self._profile_position_for_target(target),
            })
            result = view.board.rule_engine.try_interaction(obj, target, {
                "board": view.board,
                "drop_relation": relation,
            })
            if result is not None:
                source_label = getattr(obj, "label", None)
                target_label_before = getattr(target, "label", None)
                before_ids = set(id(item) for item in list(view.board.objects))

                self._drag_history_label = (
                    getattr(result, "undo_label", "") or "Merge tiles"
                )
                view.board.apply_result(result, source=obj, target=target, context={
                    "drop_relation": relation,
                    "target": target,
                    "record_history": (
                        getattr(self, "_drag_history_before", None) is None
                    ),
                })

                spawned = [
                    item for item in list(view.board.objects)
                    if id(item) not in before_ids
                ]

                if spawned:
                    for item in spawned:
                        try:
                            view.mount_object(item)
                        except Exception:
                            pass
                    try:
                        view.board.select(spawned[-1])
                    except Exception:
                        pass

                source_was_removed = obj not in view.board.objects
                if source_was_removed:
                    view._unmount_object(obj)
                view._unmount_removed_objects()
                view.sync_all()

                for item in spawned:
                    try:
                        view.sync_object(item)
                        view_obj = getattr(getattr(item, "renderer", None), "view", None)
                        if view_obj is not None:
                            view_obj.hidden = False
                            view_obj.alpha = 1.0
                            view_obj.bring_to_front()
                    except Exception:
                        pass

                spawned_summary = []
                for item in spawned:
                    spawned_summary.append({
                        "id": getattr(item, "id", None),
                        "kind": getattr(item, "kind", None),
                        "label": getattr(item, "label", None),
                        "payload": getattr(item, "payload", None),
                        "position": getattr(item, "position", None),
                    })

                view.log_session_event(
                    "merge",
                    source_label=source_label,
                    target_label_before=target_label_before,
                    target_label_after=getattr(target, "label", None),
                    relation=relation,
                    source_removed=source_was_removed,
                    spawned=spawned_summary,
                )

                if spawned:
                    view.set_status("merged -> {}".format(getattr(spawned[-1], "label", "")))
                else:
                    view.set_status("merged into {}".format(target.label))
            else:
                # A failed targeted drop should not leave the source stacked on
                # top of the target. Old Tile Calc avoided a lot of confusing
                # behaviour by keeping failed interactions spatially tidy.
                if self.drag_start_position is not None:
                    obj.position = self.drag_start_position
                else:
                    obj.position = view.board.coords.snap(obj.position, obj)
                view.sync_object(obj)
                view.log_session_event(
                    "drop_no_rule",
                    source_label=getattr(obj, "label", None),
                    target_label=getattr(target, "label", None),
                    reverted=True,
                    position=getattr(obj, "position", None),
                )
                view.set_status("no rule for {} -> {} reverted".format(obj.kind, target.kind))
        else:
            view.sync_object(obj)
            view.log_session_event(
                "drop",
                object_id=getattr(obj, "id", None),
                object_kind=getattr(obj, "kind", None),
                object_label=getattr(obj, "label", None),
                position=getattr(obj, "position", None),
            )
            view.set_status("dropped {}".format(obj.label))

        if not source_was_removed:
            obj.set_dragging(False)
            view.sync_object(obj)

        view._set_hover_target(None)
        view.transient.clear_preview()
        self.drag_obj = None
        self.drag_start_position = None
        self.drag_offset = (0, 0)
        self.start_point = None
        self.pan_last_point = None
        self.group_drag_objects = []
        self.group_drag_start_positions = {}
        self.mode = "idle"

        self._finish_drag_history()

        # Drag/drop/merge should not open the action menu. Taps open menus;
        # drags leave the board clear so the result is easier to see.
        view.transient.hide_action_dock()

    def _reset_live_merge_intent(self, obj=None):
        """Reset live directional merge intent for a new drag."""
        self._intent_direction = None
        self._intent_target_id = None
        self._intent_trail_prev = None
        self._intent_inside = False
        self._intent_skip_targets = set()
        self._drag_prev_position = None
        self._drag_last_position = getattr(obj, "position", None) if obj is not None else None

        if obj is None:
            return

        board = self.view.board
        try:
            grid = float(getattr(board.coords, "grid", 60) or 60)
        except Exception:
            grid = 60.0

        radius = grid * self.merge_entry_radius_mult
        pos = getattr(obj, "position", None)
        if pos is None:
            return

        # Old Tile Calc lesson: if we begin already near a target, do not
        # immediately arm that target. It becomes eligible after we exit.
        for candidate in list(getattr(board, "objects", []) or []):
            if candidate is obj:
                continue
            if getattr(candidate, "position", None) is None:
                continue
            try:
                if self.merge_distance(obj, candidate, pos) <= radius:
                    self._intent_skip_targets.add(id(candidate))
            except Exception:
                pass

    def _angle_to_direction(self, origin, point):
        ox, oy = origin
        px, py = point
        dx = px - ox
        dy = -(py - oy)
        deg = math.degrees(math.atan2(dy, dx)) % 360.0
        dirs = [
            "right", "top_right", "above", "top_left",
            "left", "bottom_left", "below", "bottom_right",
        ]
        return dirs[int((deg + 22.5) % 360.0 / 45.0)]

    def _movement_direction(self, start, end):
        if start is None or end is None:
            return None
        sx, sy = start
        ex, ey = end
        dx = ex - sx
        dy = ey - sy
        if abs(dx) < 0.0001 and abs(dy) < 0.0001:
            return None
        if abs(dx) >= abs(dy):
            return "right" if dx > 0 else "left"
        return "below" if dy > 0 else "above"

    def _update_live_merge_intent(self, dragged, target):
        """Update live target-entry direction.

        This is the TileKit version of old Tile Calc's birch tracker, but tuned
        for the rebuilt framework:

        - nearby-start targets are skipped until the drag exits;
        - entering a target radius arms a direction;
        - while still inside the radius, moving around the target updates the
          direction live;
        - exact-centre overlap preserves the last meaningful direction instead
          of collapsing to the arbitrary zero-vector "right" default;
        - exiting clears the live direction so a later re-entry can choose a new
          one.

        The important behaviour is that the merge direction is not frozen at
        drag start. A user can drag in one way, keep holding, move around the
        target, and release with a different directional merge.
        """
        board = self.view.board
        try:
            grid = float(getattr(board.coords, "grid", 60) or 60)
        except Exception:
            grid = 60.0

        radius = grid * self.merge_entry_radius_mult
        dead_zone = grid * 0.12

        curr = getattr(dragged, "position", None)
        target_pos = getattr(target, "position", None)
        if curr is None or target_pos is None:
            return

        def dist(a, b):
            ax, ay = a
            bx, by = b
            return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

        target_id = id(target)

        if self._intent_target_id != target_id:
            self._intent_target_id = target_id
            self._intent_direction = None
            self._intent_inside = False
            self._intent_trail_prev = None

        prev = self._intent_trail_prev
        d_curr = dist(curr, target_pos)
        inside = d_curr <= radius

        # If the drag began already close to this target, do not arm it until
        # the dragged tile leaves the radius. This ports the old skip-target
        # behaviour and prevents accidental immediate merges.
        if target_id in self._intent_skip_targets:
            if not inside:
                self._intent_skip_targets.discard(target_id)
                self._intent_inside = False
                self._intent_direction = None
            self._intent_trail_prev = curr
            return

        if prev is not None:
            d_prev = dist(prev, target_pos)

            if d_prev > radius and inside:
                # Entry crossing: calculate the boundary point like old Tile
                # Calc did, so the first armed direction feels natural.
                lo, hi = 0.0, 1.0
                for _ in range(16):
                    mid = (lo + hi) / 2.0
                    px = prev[0] + (curr[0] - prev[0]) * mid
                    py = prev[1] + (curr[1] - prev[1]) * mid
                    if dist((px, py), target_pos) > radius:
                        lo = mid
                    else:
                        hi = mid

                mid = (lo + hi) / 2.0
                crossing = (
                    prev[0] + (curr[0] - prev[0]) * mid,
                    prev[1] + (curr[1] - prev[1]) * mid,
                )
                self._intent_direction = self._angle_to_direction(target_pos, crossing)

            elif d_prev <= radius and not inside:
                # Leaving the radius deliberately clears the direction. A later
                # re-entry should be allowed to choose a different merge.
                self._intent_inside = False
                self._intent_direction = None
                self._intent_trail_prev = curr
                return

        if inside:
            # While inside the target radius, update direction live from the
            # current side, but only when the current point is meaningfully away
            # from the target centre. At exact/near-exact overlap the angle is
            # undefined; preserve the last real direction instead.
            if d_curr > dead_zone:
                self._intent_direction = self._angle_to_direction(target_pos, curr)
            self._intent_inside = True
        else:
            self._intent_inside = False

        self._intent_trail_prev = curr

    def _profile_position_for_target(self, target):
        if target is not None and id(target) == self._intent_target_id:
            return self._intent_direction
        return None

    def merge_distance(self, source, target, position=None):
        """Distance seam for app-specific interaction footprints."""
        return self.view.board.coords.distance(
            source.position if position is None else position, target.position)

    def _nearest_drop_target(self, obj, point=None, radius_mult=None, require_rule=False):
        """Return a nearby merge target, not just one directly under the pointer."""
        view = self.view
        board = view.board

        if point is not None:
            try:
                direct = view.object_at_point(point, excluding=obj)
                if direct is not None:
                    return direct
            except Exception:
                pass

        pos = getattr(obj, "position", None)
        if pos is None:
            pos = point
        if pos is None:
            return None

        try:
            grid = float(getattr(board.coords, "grid", 60) or 60)
        except Exception:
            grid = 60.0

        if radius_mult is None:
            radius_mult = self.merge_release_radius_mult

        radius = grid * float(radius_mult or 1.0)
        best = None
        best_dist = None

        for candidate in reversed(list(getattr(board, "objects", []) or [])):
            if candidate is obj:
                continue
            if getattr(candidate, "position", None) is None:
                continue

            try:
                dist = self.merge_distance(obj, candidate, pos)
            except Exception:
                continue

            if dist > radius:
                continue

            if require_rule:
                try:
                    relation = board.coords.relation(obj, candidate, {
                        "drag_start_position": self.drag_start_position,
                        "profile_position": self._profile_position_for_target(candidate),
                    })
                    preview = self.preview_interaction(obj, candidate, {
                        "board": board,
                        "drop_relation": relation,
                    })
                    result = None if (preview is not None or getattr(self, "preview_only_target_checks", False)) else board.rule_engine.try_interaction(obj, candidate, {
                        "board": board,
                        "drop_relation": relation,
                    })
                    if preview is None and result is None:
                        continue
                except Exception:
                    continue

            if best_dist is None or dist < best_dist:
                best = candidate
                best_dist = dist

        return best


    def _distance_to_segment(self, point, start, end):
        """Return distance from point to finite segment start->end."""
        try:
            px, py = point
            ax, ay = start
            bx, by = end
            vx = bx - ax
            vy = by - ay
            wx = px - ax
            wy = py - ay
            denom = vx * vx + vy * vy
            if denom <= 0:
                dx = px - ax
                dy = py - ay
                return (dx * dx + dy * dy) ** 0.5
            t = (wx * vx + wy * vy) / float(denom)
            t = max(0.0, min(1.0, t))
            cx = ax + t * vx
            cy = ay + t * vy
            dx = px - cx
            dy = py - cy
            return (dx * dx + dy * dy) ** 0.5
        except Exception:
            return 999999.0

    def preview_interaction(self, source, target, context):
        """App-overridable live hint; default keeps full rule previews."""
        return self.view.board.rule_engine.preview_interaction(source, target, context)

    def _resolve_drop_target(self, obj, point=None, for_preview=False):
        """Return the best live drop target for obj.

        This deliberately does more than point hit-testing. Directional profile
        merges often release adjacent to the target, so we look for nearby valid
        rule candidates and prefer the candidate closest to the drag segment.

        It stays generic: TileKit asks the app rule engine whether a candidate is
        meaningful; TileKit does not know calculator rules.
        """
        view = self.view
        board = view.board

        fallback = None
        try:
            fallback = view.object_at_point(point, excluding=obj) if point is not None else None
        except Exception:
            fallback = None

        if obj is None:
            return fallback

        start = self.drag_start_position
        end = getattr(obj, "position", None)
        if end is None:
            return fallback

        try:
            grid = float(getattr(board.coords, "grid", 60) or 60)
        except Exception:
            grid = 60.0

        max_dist = grid * 1.35
        candidates = []

        for target in list(getattr(board, "objects", []) or []):
            if target is obj:
                continue
            if getattr(target, "position", None) is None:
                continue

            try:
                dist_to_obj = self.merge_distance(obj, target, end)
            except Exception:
                dist_to_obj = 999999.0

            if dist_to_obj > max_dist:
                continue

            try:
                relation = board.coords.relation(obj, target, {
                    "drag_start_position": start,
                })
                ctx = {
                    "board": board,
                    "drop_relation": relation,
                }
                preview = self.preview_interaction(obj, target, ctx)
                if preview is None:
                    continue

                seg_dist = self._distance_to_segment(target.position, start or end, end)
                # Prefer targets the drag path actually passed through, then
                # closer targets, then current direct hit.
                direct_hit_bonus = 0 if target is fallback else 1
                candidates.append((seg_dist, dist_to_obj, direct_hit_bonus, target))
            except Exception:
                continue

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return candidates[0][3]

        return fallback

    def _current_group(self):
        try:
            selection = getattr(self.view.board, "selection", None)
            return list(getattr(selection, "group", []) or [])
        except Exception:
            return []

    def _rect_from_points(self, a, b):
        ax, ay = a
        bx, by = b
        return (ax, ay, bx - ax, by - ay)

    def _normalise_rect(self, rect):
        x, y, w, h = rect
        if w < 0:
            x = x + w
            w = -w
        if h < 0:
            y = y + h
            h = -h
        return (x, y, w, h)

    def cancelled(self, event):
        self._cancel_drag_history()
        view = self.view
        obj = self.drag_obj
        if obj is not None:
            obj.set_dragging(False)
            view.sync_object(obj)

        for item in list(self.group_drag_objects):
            try:
                item.set_dragging(False)
                view.sync_object(item)
            except Exception:
                pass

        view._set_hover_target(None)
        view.set_status("cancelled")
        self.drag_obj = None
        self.drag_start_position = None
        self.drag_offset = (0, 0)
        self.start_point = None
        self.pointer_start_position = None
        self.pan_last_point = None
        self.group_drag_objects = []
        self.group_drag_start_positions = {}
        self.mode = "idle"
        view._update_action_dock()
