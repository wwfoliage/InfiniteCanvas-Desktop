from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "static" / "js" / "smart-canvas.js"


class SmartCanvasDirectReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def function_source(self, name):
        match = re.search(
            rf"function {name}\([^)]*\)\{{.*?\n\}}",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, f"{name} was not found")
        return match.group(0)

    def test_input_mention_candidates_use_visible_reference_row(self):
        body = self.function_source("inputMentionCandidateImages")
        self.assertIn("visibleReferenceImagesFor(node)", body)
        self.assertNotIn("directConnectedMediaFor(node)", body)
        self.assertNotIn("lineImagesFor(node)", body)

    def test_visible_row_and_request_use_shared_authorization(self):
        visible = self.function_source("visibleReferenceImagesFor")
        request = self.function_source("buildPromptRequest")
        self.assertIn("allowedMentionedImagesFromPrompt(node)", visible)
        authorization = request.index("if(!isAllowedMentionReference(node, part, ctx))")
        append_reference = request.index("refs.push", authorization)
        self.assertLess(authorization, append_reference)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_input_mention_candidates_keep_self_media_and_dedupe(self):
        function = self.function_source("inputMentionCandidateImages")
        script = function + r'''
function visibleReferenceImagesFor(){
  return [
    {url:'self.png', nodeId:'C', kind:'image', name:'当前图片'},
    {url:'self.mp4', nodeId:'C', kind:'video', name:'当前视频'},
    {url:'direct.png', nodeId:'B', kind:'image', name:'直接图片'},
    {url:'self.png', nodeId:'C', kind:'image', name:'重复图片'}
  ];
}
const items = inputMentionCandidateImages({id:'C'});
const urls = items.map(item => item.url);
if (JSON.stringify(urls) !== JSON.stringify(['self.png','self.mp4','direct.png'])) {
  throw new Error(`unexpected candidates: ${urls}`);
}
if (items[0].alias !== '当前图片' || items[1].kind !== 'video') {
  throw new Error('candidate metadata was not preserved');
}
'''
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_direct_graph_asset_exception_and_media_types(self):
        names = [
            "directReferenceNodesFor",
            "directReferenceNodeIdsFor",
            "directConnectedMediaFor",
            "isAssetMentionReference",
            "isAllowedMentionReference",
        ]
        functions = "\n".join(self.function_source(name) for name in names)
        script = functions + r'''
const nodes = [
  {id:'A', images:[{url:'a.png', kind:'image'}]},
  {id:'B', images:[{url:'b.png', kind:'image'}, {url:'b.mp4', kind:'video'}]},
  {id:'C', images:[]},
  {id:'D', images:[{url:'d.png', kind:'image'}]},
];
const canvas = {connections:[
  {from:'A', to:'B', kind:'input'},
  {from:'B', to:'C', kind:'input'},
]};
const smartLoopContext = null;
function smartImageUsesWorkflowInput(){ return false; }
function inputNodesFor(node){
  return canvas.connections
    .filter(conn => conn.to === node.id && (conn.kind || 'flow') === 'input')
    .map(conn => nodes.find(item => item.id === conn.from))
    .filter(Boolean);
}
function workflowInputNodesFor(node){ return inputNodesFor(node); }
function imagesForNode(node){
  return (node.images || []).map((item, imageIndex) => ({...item, nodeId:node.id, imageIndex}));
}
function outputImagesForNode(node){ return imagesForNode(node); }

const current = nodes.find(node => node.id === 'C');
const ids = [...directReferenceNodeIdsFor(current)];
if (JSON.stringify(ids) !== JSON.stringify(['B'])) throw new Error(`unexpected ids: ${ids}`);

const urls = directConnectedMediaFor(current).map(item => item.url);
if (JSON.stringify(urls) !== JSON.stringify(['b.png','b.mp4'])) throw new Error(`unexpected media: ${urls}`);

if (!isAllowedMentionReference(current, {url:'b.png', nodeId:'B'})) throw new Error('direct reference rejected');
if (isAllowedMentionReference(current, {url:'a.png', nodeId:'A'})) throw new Error('ancestor reference allowed');
if (isAllowedMentionReference(current, {url:'d.png', nodeId:'D'})) throw new Error('unconnected reference allowed');
if (!isAllowedMentionReference(current, {url:'asset.png', nodeId:'', asset_uris:{}})) throw new Error('asset reference rejected');
if (isAllowedMentionReference(current, {url:'d.png', nodeId:'D', asset_uris:{api:'asset://d'}})) throw new Error('canvas node bypassed boundary through asset metadata');
'''
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
