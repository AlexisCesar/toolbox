import asyncio
import tomllib

from textual.containers import VerticalScroll
from textual.widgets import Button, Input, OptionList
from textual.widgets import TextArea

from src.tui import ToolboxTUI
from src.utils.config import config
from src.utils.script_description_dialog import ScriptDescriptionDialog
from src.utils.script_editor_dialog import ScriptEditorDialog
from src.views.scripts import Scripts


def test_scripts_are_grouped_searchable_and_show_selected_actions(tmp_path, monkeypatch) -> None:
    scripts_dir = tmp_path / "my-scripts"
    sql_script = scripts_dir / "db-scripts" / "sql-server" / "query.sql"
    python_script = scripts_dir / "python" / "report.py"
    root_script = scripts_dir / "root.py"
    for script in (sql_script, python_script, root_script):
        script.parent.mkdir(parents=True, exist_ok=True)
        content = "-- sample SQL\n" if script.suffix == ".sql" else "# sample Python\n"
        script.write_text(content, encoding="utf-8")
    (scripts_dir / "scripts_configuration.toml").write_text(
        '["db-scripts/sql-server/query.sql"]\n'
        'description = "database read query"\n'
        'latest_parameters = "preserved value"\n\n'
        '["python/report.py"]\n'
        'description = "Python report"\n'
        'latest_parameters = "--limit 5"\n',
        encoding="utf-8",
    )

    monkeypatch.setitem(config._data["paths"], "scripts", str(scripts_dir))
    monkeypatch.setitem(config._data["scripts"], "depth", 4)
    app = ToolboxTUI()

    async def check_workflow() -> None:
        async with app.run_test(size=(140, 45)) as pilot:
            app.action_select_view(3)
            await pilot.pause()

            assert isinstance(app.query_one("#script-details-scroll"), VerticalScroll)
            search = app.query_one("#script-search", Input)
            script_list = app.query_one("#script-list", OptionList)
            assert script_list.option_count == 6
            assert script_list.get_option_index("folder:db-scripts/sql-server") == 0
            assert script_list.get_option_index("folder:python") is not None
            assert script_list.get_option_index("folder:.") is not None

            search.value = "database read"
            await pilot.pause()
            assert script_list.option_count == 2
            assert script_list.get_option_index(
                "db-scripts/sql-server/query.sql"
            ) == 1
            script_list.focus()
            script_list.highlighted = script_list.get_option_index(
                "db-scripts/sql-server/query.sql"
            )
            await pilot.press("enter")
            await pilot.pause()

            assert app.query_one("#script-copy", Button).disabled is False
            assert app.query_one("#script-copy", Button).styles.display == "block"
            assert app.query_one("#script-run", Button).styles.display == "none"
            assert app.query_one("#script-open-edit", Button).disabled is False
            assert app.query_one("#script-update-description", Button).disabled is False

            await pilot.click("#script-update-description")
            await pilot.pause()
            assert isinstance(app.screen, ScriptDescriptionDialog)
            description_input = app.screen.query_one("#script-description-input", TextArea)
            assert description_input.text == "database read query"
            description_input.text = "database read query, updated"
            await pilot.click("#script-description-save")
            await pilot.pause()

            saved_config = tomllib.loads(
                (scripts_dir / "scripts_configuration.toml").read_text(encoding="utf-8")
            )
            assert saved_config["db-scripts/sql-server/query.sql"]["description"] == (
                "database read query, updated"
            )
            assert saved_config["db-scripts/sql-server/query.sql"]["latest_parameters"] == (
                "preserved value"
            )
            assert saved_config["python/report.py"]["latest_parameters"] == "--limit 5"
            assert app.query_one("#scripts-view", Scripts).selected_script.name == "query.sql"

            search.value = "report.py"
            await pilot.pause()
            assert script_list.option_count == 2
            script_list.focus()
            script_list.highlighted = script_list.get_option_index("python/report.py")
            await pilot.press("enter")
            await pilot.pause()

            assert app.query_one("#script-run", Button).disabled is False
            assert app.query_one("#script-run-external", Button).disabled is False
            assert app.query_one("#script-run-parameters", Button).disabled is False
            assert app.query_one("#script-copy", Button).styles.display == "none"
            assert app.query_one("#script-open-edit", Button).disabled is False
            assert app.query_one("#script-update-description", Button).disabled is False

            details_scroll = app.query_one("#script-details-scroll", VerticalScroll)
            details_scroll.scroll_end(animate=False)
            await pilot.pause()
            assert await pilot.click("#script-open-edit")
            await pilot.pause()
            assert isinstance(app.screen, ScriptEditorDialog)
            assert app.screen.query_one("#script-editor-content", TextArea).text == (
                "# sample Python\n"
            )
            await pilot.click("#script-editor-cancel")
            await pilot.pause()

    asyncio.run(check_workflow())


def test_update_description_requires_scripts_configuration(tmp_path, monkeypatch) -> None:
    scripts_dir = tmp_path / "my-scripts"
    scripts_dir.mkdir()
    (scripts_dir / "example.py").write_text("# sample\n", encoding="utf-8")
    monkeypatch.setitem(config._data["paths"], "scripts", str(scripts_dir))
    monkeypatch.setitem(config._data["scripts"], "depth", 0)
    app = ToolboxTUI()

    async def check_workflow() -> None:
        async with app.run_test(size=(100, 35)) as pilot:
            app.action_select_view(3)
            await pilot.pause()
            script_list = app.query_one("#script-list", OptionList)
            script_list.focus()
            script_list.highlighted = script_list.get_option_index("example.py")
            await pilot.press("enter")
            await pilot.pause()

            assert app.query_one("#script-open-edit", Button).disabled is False
            assert app.query_one("#script-update-description", Button).disabled is True
            details_scroll = app.query_one("#script-details-scroll", VerticalScroll)
            assert details_scroll.max_scroll_y > 0

    asyncio.run(check_workflow())
