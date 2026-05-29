from typing import Optional, Protocol


class LayoutProvider(Protocol):
    """Strategy for retrieving layout data. Implementations: AccessibilityProvider, JdwpProvider."""

    def get_layout_tree(self, max_depth: Optional[int] = None,
                        filter_class: Optional[str] = None) -> str:
        ...

    def get_element_details(self, selector_type: str, selector_value: str,
                            timeout: float = 5.0) -> str:
        ...
