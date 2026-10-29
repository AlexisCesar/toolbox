"""Searchable catalog of small, offline developer utilities."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from src.utils.offline_utilities import UTILITIES, Utility, run_utility
from src.utils.logger import Logger


class UtilityDialog(ModalScreen[None]):
    """Run a selected utility in a focused modal window."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, utility: Utility, logger: Logger) -> None:
        super().__init__()
        self.utility = utility
        self.logger = logger

    def compose(self) -> ComposeResult:
        with Vertical(id="utility-dialog"):
            yield Label(self.utility.name, id="utility-dialog-title")
            yield Static(self.utility.description, id="utility-dialog-description")
            if self.utility.option_label:
                yield Label(self.utility.option_label, classes="utility-field-label")
                yield Input(value=self.utility.option_default, id="utility-option-input")
            elif self.utility.second_input_label:
                with Horizontal(id="utility-inputs-row"):
                    with Vertical(classes="utility-input-column"):
                        yield Label(self.utility.input_label, classes="utility-field-label")
                        yield TextArea("", id="utility-input", soft_wrap=True)
                    with Vertical(classes="utility-input-column"):
                        yield Label(self.utility.second_input_label, classes="utility-field-label")
                        yield TextArea("", id="utility-second-input", soft_wrap=True)
            else:
                yield Label(self.utility.input_label, classes="utility-field-label")
                yield TextArea("", id="utility-input", soft_wrap=True)
            yield Label("Result", classes="utility-field-label")
            yield TextArea("", id="utility-output", read_only=True, soft_wrap=True)
            with Horizontal(id="utility-dialog-buttons"):
                yield Button("Run", variant="primary", id="utility-run")
                yield Button("Close", id="utility-close")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "utility-run":
            self.run()
        elif event.button.id == "utility-close":
            self.action_close()

    def run(self) -> None:
        """Run the tool and display either its result or a useful input error."""
        text_area = (
            self.query_one("#utility-input", TextArea)
            if self.utility.option_label is None
            else None
        )
        second_area = (
            self.query_one("#utility-second-input", TextArea)
            if self.utility.second_input_label
            else None
        )
        option_input = (
            self.query_one("#utility-option-input", Input)
            if self.utility.option_label
            else None
        )
        try:
            result = run_utility(
                self.utility.id,
                text=text_area.text if text_area else "",
                second_text=second_area.text if second_area else "",
                option=option_input.value if option_input else "",
            )
        except (ValueError, SyntaxError) as error:
            result = f"Error: {error}"
            self.logger.warn(f"Offline utility {self.utility.name} rejected its input: {error}")
        else:
            self.logger.info(f"Ran offline utility: {self.utility.name}.")
        self.query_one("#utility-output", TextArea).load_text(result)

    def action_close(self) -> None:
        self.dismiss()


class Utilities(Static):
    """Browse and open utilities grouped by purpose."""

    def __init__(self, logger: Logger, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = logger
        self.selected_utility: Utility | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="utilities-container"):
            yield Label("Offline Utilities", id="utilities-title")
            yield Static(
                "Search the catalog, select a tool, then open it to work with local input.",
                id="utilities-subtitle",
            )
            yield Input(placeholder="Search by name or description…", id="utility-search")
            with Horizontal(id="utilities-browser"):
                yield OptionList(id="utility-list")
                with Vertical(id="utility-details"):
                    yield Label("Select a utility", id="utility-details-title")
                    yield Static(
                        "Choose a tool from the list to see what it does.",
                        id="utility-details-description",
                    )
                    yield Button("Open utility", variant="primary", id="utility-open", disabled=True)

    def on_mount(self) -> None:
        self._populate_list("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "utility-search":
            self._populate_list(event.value)

    def _populate_list(self, query: str) -> None:
        utility_list = self.query_one("#utility-list", OptionList)
        utility_list.clear_options()
        self.selected_utility = None
        self.query_one("#utility-open", Button).disabled = True
        self.query_one("#utility-details-title", Label).update("Select a utility")
        self.query_one("#utility-details-description", Static).update(
            "Choose a tool from the list to see what it does."
        )

        normalized_query = query.casefold().strip()
        visible = [
            utility
            for utility in UTILITIES
            if normalized_query in f"{utility.name} {utility.description} {utility.category}".casefold()
        ]
        categories: dict[str, list[Utility]] = {}
        for utility in visible:
            categories.setdefault(utility.category, []).append(utility)
        for category, utilities in categories.items():
            utility_list.add_option(
                Option(Text(category, style="bold"), id=f"category-{category}", disabled=True)
            )
            utility_list.add_options(
                Option(f"  {utility.name}  —  {utility.description}", id=utility.id)
                for utility in utilities
            )
        if not visible:
            utility_list.add_option(
                Option("No utilities match this search.", id="no-results", disabled=True)
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        utility_id = event.option.id
        self.selected_utility = next(
            (utility for utility in UTILITIES if utility.id == utility_id), None
        )
        if self.selected_utility is None:
            return
        self.query_one("#utility-details-title", Label).update(self.selected_utility.name)
        self.query_one("#utility-details-description", Static).update(
            f"{self.selected_utility.category}\n\n{self.selected_utility.description}"
        )
        self.query_one("#utility-open", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "utility-open" or self.selected_utility is None:
            return
        self.logger.info(f"Opened offline utility: {self.selected_utility.name}.")
        self.app.push_screen(UtilityDialog(self.selected_utility, self.logger))
