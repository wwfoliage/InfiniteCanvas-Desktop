from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMART_CANVAS_JS = ROOT / "static" / "js" / "smart-canvas.js"


class SmartUploadExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SMART_CANVAS_JS.read_text(encoding="utf-8")

    def test_collapsed_upload_node_expands_before_opening_picker(self):
        match = re.search(
            r"nodeDrop\?\.addEventListener\('click', e => \{.*?\n\s*\}\);",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "upload node click handler was not found")
        handler = match.group(0)

        selection_check = handler.index(
            "const wasExpanded = expandedUploadNodeId === id && isNodeSelected(id);"
        )
        mark_expanded = handler.index("expandedUploadNodeId = id;")
        expand_guard = handler.index("if(!wasExpanded) return;")
        picker = handler.index("pickMediaForSmartNode(id);")
        self.assertLess(selection_check, mark_expanded)
        self.assertLess(mark_expanded, expand_guard)
        self.assertLess(expand_guard, picker)

    def test_existing_selection_does_not_count_as_user_expansion(self):
        self.assertIn("let expandedUploadNodeId = '';", self.source)
        self.assertNotIn("const wasExpanded = isNodeSelected(id);", self.source)
        self.assertIn(
            "expandedUploadNodeId = el.querySelector('.node-drop') ? id : '';",
            self.source,
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the interaction test")
    def test_preselected_node_still_needs_two_upload_box_clicks(self):
        match = re.search(
            r"nodeDrop\?\.addEventListener\('click', (e => \{.*?\n\s*\})\);",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "upload node click handler was not found")
        handler = match.group(1)
        script = f"""
let expandedUploadNodeId = '';
let uploadTargetId = '';
let pendingGroupUploadPoint = null;
let selectedId = 'upload-1';
let selectedIds = [];
let selectedImage = {{nodeId:'', index:-1}};
const id = 'upload-1';
const nodes = [{{id}}];
let pickerCalls = 0;
function isNodeSelected(value) {{ return selectedId === value || selectedIds.includes(value); }}
function hideRunTimerForNode() {{}}
function syncSelectionUi() {{}}
function updateComposer() {{}}
function pickMediaForSmartNode() {{ pickerCalls++; }}
const clickUpload = {handler};
const event = {{preventDefault() {{}}, stopPropagation() {{}}}};
clickUpload(event);
if (pickerCalls !== 0) throw new Error('first click opened the picker');
clickUpload(event);
if (pickerCalls !== 1) throw new Error('second click did not open the picker');
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
