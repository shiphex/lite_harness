import main


def test_main_prints_project_name_and_runs_master_agent(monkeypatch, capsys):
    calls = []
    import core

    monkeypatch.setattr(core, "master_agent", lambda: calls.append("run"))

    main.main()

    assert capsys.readouterr().out == "Hello from lite_harness!\n"
    assert calls == ["run"]
