from abstract_tools.resources import resource_path


def test_resource_path_points_at_bundled_template():
    path = resource_path("Template File Documents.xlsx")
    assert path.exists()
    assert path.name == "Template File Documents.xlsx"
