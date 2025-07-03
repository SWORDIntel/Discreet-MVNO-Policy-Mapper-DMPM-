"""Unit tests for export functionality"""
import pytest
from unittest.mock import Mock, patch
import os
import pandas as pd # Assuming pandas is used for CSV/Excel, add to deps if not
from ghost_dmpm.enhancements.export import GhostExporter
from ghost_dmpm.core.config import GhostConfig

@pytest.fixture
def exporter():
    config = Mock(spec=GhostConfig)
    config.get_logger.return_value = Mock()
    config.get_absolute_path.side_effect = lambda x: x # Simple mock for path resolution
    return GhostExporter(config)

def test_export_initialization(exporter):
    """Test exporter initialization"""
    assert exporter.config is not None

def test_export_csv(exporter, tmp_path):
    """Test CSV export"""
    data = [{"name": "MVNO1", "score": 1.0}, {"name": "MVNO2", "score": 2.5}]
    df = pd.DataFrame(data)
    output_path = tmp_path / "test_export.csv"

    # Mocking Path.write_text for exporter._save_file
    with patch('pathlib.Path.write_text') as mock_write_text:
        exporter.export_csv(df, str(output_path))
        mock_write_text.assert_called_once()
    # In a real test, we'd check the content of mock_write_text.call_args[0][0]

def test_export_json(exporter, tmp_path):
    """Test JSON export"""
    data = {"mvnos": [{"name": "MVNO1", "score": 1.0}]}
    output_path = tmp_path / "test_export.json"

    with patch('pathlib.Path.write_text') as mock_write_text:
        exporter.export_json(data, str(output_path))
        mock_write_text.assert_called_once()
    # Check content of json.dumps(data, indent=4)

def test_export_html(exporter, tmp_path):
    """Test HTML export"""
    # Assuming HTML export uses a template rendering mechanism
    data = {"title": "Test Report", "items": ["item1", "item2"]}
    template_name = "mock_template.html" # GhostExporter might have a default
    output_path = tmp_path / "test_export.html"

    # If GhostExporter uses Jinja2 or similar, mock that.
    # For a simple file save:
    with patch.object(GhostExporter, '_render_template', return_value="<html>Mock Content</html>") as mock_render, \
         patch('pathlib.Path.write_text') as mock_write_text:
        exporter.export_html(data, str(output_path), template_name)
        mock_render.assert_called_once_with(template_name, data)
        mock_write_text.assert_called_once_with("<html>Mock Content</html>", encoding='utf-8')

# Add more test stubs for other formats (Excel, PDF if re-enabled)
# and for error handling, edge cases, etc.
