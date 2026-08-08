"""Web browser integration for Material Combiner.

This module provides an operator for opening URLs in the user's external web browser,
with validation to ensure security and correct formatting of URLs. It's used for
accessing documentation, support resources, and sponsor links.

Usage example:
    bpy.ops.smc.browser(link=r"https://github.com/Alrauna/material-combiner-addon")
"""

import webbrowser
from typing import Set, Tuple
from urllib.parse import urlsplit

import bpy
from bpy.props import StringProperty

class OpenBrowser(bpy.types.Operator):
    """Opens a web browser with the specified URL.

    This operator validates the URL for correct formatting and security
    concerns before attempting to open it in the user's default web browser.
    It provides error handling and requires a complete HTTPS URL.
    """

    bl_idname = "smc.browser"
    bl_label = "Open Web Browser"
    bl_description = "Open the specified URL in your default web browser"

    link = StringProperty(
        name="URL", description="Web address to open", default=""
    )

    def execute(self, context: bpy.types.Context) -> Set[str]:
        """Execute the URL opening operation.

        Validates the URL first, then attempts to open it in the default browser.

        Args:
            context: Current Blender context.

        Returns:
            Set containing operation status.
        """
        valid, message = self._validate_url()
        if not valid:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        try:
            webbrowser.open(self.link, new=2, autoraise=True)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, "Failed to open browser: {}".format(str(e)))
            return {"CANCELLED"}

    def _validate_url(self) -> Tuple[bool, str]:
        """Validate the URL for correctness and security.

        Checks that the URL is a complete HTTPS address without credentials,
        whitespace, or control characters.

        Returns:
            Tuple containing (is_valid, error_message).
        """
        if not self.link:
            return False, "URL cannot be empty"
        if any(
            character.isspace() or ord(character) < 32
            for character in self.link
        ):
            return (
                False,
                "URL cannot contain whitespace or control characters",
            )
        try:
            parsed = urlsplit(self.link)
            _ = parsed.port
        except ValueError:
            return False, "Invalid HTTPS URL"
        if parsed.scheme != "https" or not parsed.hostname:
            return False, "URL must be a complete HTTPS address"
        if parsed.username is not None or parsed.password is not None:
            return False, "URL credentials are not allowed"

        return True, ""
