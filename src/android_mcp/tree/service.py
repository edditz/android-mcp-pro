from android_mcp.tree.views import TreeState, ElementNode, CenterCord, BoundingBox
from android_mcp.tree.utils import extract_cordinates,get_center_cordinates
from android_mcp.tree.config import INTERACTIVE_CLASSES
from PIL import Image, ImageFont, ImageDraw
from xml.etree.ElementTree import Element
from xml.etree import ElementTree
from typing import TYPE_CHECKING
import random
import re
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if TYPE_CHECKING:
    from android_mcp.mobile import Mobile

class Tree:
    def __init__(self,mobile:'Mobile'):
        self.mobile = mobile

    def get_element_tree(self, xml_data=None)->'Element':
        tree_string = xml_data if xml_data else self.mobile.device.dump_hierarchy()
        return ElementTree.fromstring(tree_string)

    def get_layout_tree(self, xml_data=None, max_depth=None):
        """Parse full view hierarchy into a LayoutNode tree.

        When max_depth is None, the entire hierarchy is traversed with no depth limit.
        """
        from android_mcp.tree.views import LayoutNode, BoundingBox

        element_tree = self.get_element_tree(xml_data=xml_data)

        # Skip the <hierarchy> wrapper
        if element_tree.tag == 'hierarchy':
            if len(element_tree) == 1:
                element_tree = element_tree[0]
            elif len(element_tree) > 1:
                from xml.etree.ElementTree import Element
                virtual_root = Element('node', {
                    'class': 'hierarchy',
                    'resource-id': '',
                    'bounds': '[0,0][0,0]',
                    'enabled': 'true',
                    'visible-to-user': 'true',
                    'clickable': 'false',
                    'focused': 'false',
                    'checked': 'false',
                    'scrollable': 'false',
                    'text': '',
                    'content-desc': '',
                })
                virtual_root.extend(element_tree)
                element_tree = virtual_root

        def parse_node(node, depth):
            bounds_match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
            if bounds_match:
                x1, y1, x2, y2 = map(int, bounds_match.groups())
                bounds = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
            else:
                bounds = BoundingBox(x1=0, y1=0, x2=0, y2=0)

            raw_id = node.get('resource-id', '')
            short_id = raw_id.split('/')[-1] if '/' in raw_id else raw_id

            children = ()
            if max_depth is None or depth < max_depth:
                child_nodes = [parse_node(child, depth + 1) for child in node]
                children = tuple(c for c in child_nodes if c is not None)

            return LayoutNode(
                class_name=node.get('class', ''),
                resource_id=short_id,
                bounds=bounds,
                text=node.get('text', ''),
                content_desc=node.get('content-desc', ''),
                enabled=node.get('enabled', 'false') == 'true',
                visible=node.get('visible-to-user', 'false') == 'true',
                clickable=node.get('clickable', 'false') == 'true',
                focused=node.get('focused', 'false') == 'true',
                checked=node.get('checked', 'false') == 'true',
                scrollable=node.get('scrollable', 'false') == 'true',
                depth=depth,
                children=children,
            )

        return parse_node(element_tree, 0)

    @staticmethod
    def format_layout_tree(root):
        """Format a LayoutNode tree as indented text for AI consumption."""
        lines = []

        def format_node(node, indent=0):
            prefix = "  " * indent
            short_class = node.class_name.split('.')[-1] if '.' in node.class_name else node.class_name
            parts = [f"[{node.depth}] {short_class}  {node.bounds.to_string()}"]

            if node.resource_id:
                parts.append(f"id={node.resource_id}")
            if node.text:
                parts.append(f"text={node.text}")
            if node.content_desc:
                parts.append(f"desc={node.content_desc}")
            if node.clickable:
                parts.append("clickable=true")
            if node.scrollable:
                parts.append("scrollable=true")
            if node.focused:
                parts.append("focused=true")
            if node.checked:
                parts.append("checked=true")

            lines.append(prefix + "  ".join(parts))

            for child in node.children:
                format_node(child, indent + 1)

        format_node(root)
        return "\n".join(lines)

    def get_state(self, xml_data=None)->TreeState:
        interactive_elements=self.get_interactive_elements(xml_data=xml_data)
        return TreeState(interactive_elements=interactive_elements)
    
    def get_interactive_elements(self, xml_data=None)->list:
        interactive_elements=[]
        element_tree = self.get_element_tree(xml_data=xml_data)
        nodes=element_tree.findall('.//node[@enabled="true"]')
        for node in nodes:
            if self.is_interactive(node):
                x1,y1,x2,y2 = extract_cordinates(node)
                name=self.get_element_name(node)
                if not name:
                    continue
                x_center,y_center = get_center_cordinates((x1,y1,x2,y2))
                raw_id=node.get('resource-id','')
                short_id=raw_id.split('/')[-1] if '/' in raw_id else raw_id
                interactive_elements.append(ElementNode(**{
                    'name':name,
                    'class_name':node.get('class'),
                    'coordinates':CenterCord(x=x_center,y=y_center),
                    'bounding_box':BoundingBox(x1=x1,y1=y1,x2=x2,y2=y2),
                    'resource_id':short_id
                }))
        return interactive_elements

    def get_element_name(self, node) -> str:
        name = node.get('content-desc') or node.get('text')
        if not name:
            texts = []
            fallback_texts = []
            
            def collect_text(n):
                # Check if this node is actionable (and not the root node we started with)
                is_actionable = (n is not node) and (
                               n.get('clickable') == "true" or 
                               n.get('long-clickable') == "true" or
                               n.get('checkable') == "true" or
                               n.get('scrollable') == "true")
                
                val = n.get('text') or n.get('content-desc') or n.get('hint')

                if is_actionable:
                    if val:
                        fallback_texts.append(val)
                    return # Stop recursing into actionable nodes
                
                if val:
                    texts.append(val)
                
                for child in n:
                    collect_text(child)
            
            collect_text(node)
            
            # Use primary texts if found, otherwise use fallback texts from actionable children
            final_texts = texts if texts else fallback_texts
            name = " ".join(final_texts).strip()
        return name

    def is_interactive(self, node) -> bool:
        attributes = node.attrib
        return (attributes.get('focusable') == "true" or 
        attributes.get('clickable') == "true" or
        attributes.get('long-clickable') == "true" or
        attributes.get('checkable') == "true" or
        attributes.get('scrollable') == "true" or
        attributes.get('selected') == "true" or
        attributes.get('password') == "true" or
        attributes.get('class') in INTERACTIVE_CLASSES)

    def annotated_screenshot(self, nodes: list[ElementNode],scale:float=0.7, screenshot=None) -> Image.Image:
        if screenshot is None:
            screenshot = self.mobile.get_screenshot(scale=scale)

        draw = ImageDraw.Draw(screenshot)
        font_size = 12
        try:
            font = ImageFont.truetype('arial.ttf', font_size)
        except IOError:
            font = ImageFont.load_default()

        def get_random_color():
            return "#{:06x}".format(random.randint(0, 0xFFFFFF))

        def draw_annotation(label, node: ElementNode):
            bounding_box = node.bounding_box
            color = get_random_color()

            adjusted_box = (
                int(bounding_box.x1 * scale),
                int(bounding_box.y1 * scale),
                int(bounding_box.x2 * scale),
                int(bounding_box.y2 * scale)
            )
            # Draw bounding box
            draw.rectangle(adjusted_box, outline=color, width=2)

            # Label dimensions
            label_width = draw.textlength(str(label), font=font)
            label_height = font_size
            left, top, right, bottom = adjusted_box

            # Label position above bounding box, clamped to image bounds
            label_x1 = max(0, right - label_width)
            label_y1 = max(0, top - label_height - 4)
            label_x2 = label_x1 + label_width
            label_y2 = label_y1 + label_height + 4

            # Draw label background and text
            draw.rectangle([(label_x1, label_y1), (label_x2, label_y2)], fill=color)
            draw.text((label_x1 + 2, label_y1 + 2), str(label), fill=(255, 255, 255), font=font)

        for i, node in enumerate(nodes):
            draw_annotation(i, node)

        return screenshot
