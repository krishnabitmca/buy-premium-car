import yaml

def test_dashboard_defaults_are_real_yaml_keys():
    with open("config/settings.yaml", encoding="utf-8") as fh:
        settings = yaml.safe_load(fh)
    market = settings["market"]
    assert market["default_dashboard_budget_lakh"] == 40.0
    assert market["default_dashboard_age_years"] == 4.0
