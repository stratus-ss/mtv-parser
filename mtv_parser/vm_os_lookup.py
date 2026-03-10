import os
import yaml
from typing import Dict, Optional, Any


class VMOSLookup:
    """Load and parse VMI/VM YAML files to build OS lookup dictionary."""

    def __init__(self: "VMOSLookup", vm_yaml_dir: Optional[str] = None) -> None:
        """Initialize the VMOSLookup class.

        Args:
            vm_yaml_dir (Optional[str]): Directory containing VMI/VM YAML files. 
                                       Defaults to "./vm_yaml" if None.
        """
        self.vm_yaml_dir = vm_yaml_dir or "./vm_yaml"
        self.os_lookup: Dict[str, str] = {}

    def _extract_os_from_vmi(self: "VMOSLookup", vmi_item: Dict[str, Any]) -> Optional[str]:
        """Extract OS information from a VirtualMachineInstance resource.

        Args:
            vmi_item (Dict[str, Any]): A VMI resource dictionary.

        Returns:
            Optional[str]: OS name/identifier, or None if not found.
        """
        # Prefer guestOSInfo.prettyName (most descriptive)
        guest_os_info = vmi_item.get("status", {}).get("guestOSInfo", {})
        if guest_os_info:
            # Try prettyName first (e.g., "Red Hat Enterprise Linux 9.7 (Plow)")
            if "prettyName" in guest_os_info and guest_os_info["prettyName"]:
                return guest_os_info["prettyName"]
            # Fallback to name (e.g., "Red Hat Enterprise Linux")
            if "name" in guest_os_info and guest_os_info["name"]:
                os_name = guest_os_info["name"]
                # Append version if available for better identification
                if "version" in guest_os_info and guest_os_info["version"]:
                    os_name = f"{os_name} {guest_os_info['version']}"
                return os_name
            # Fallback to id (e.g., "rhel")
            if "id" in guest_os_info and guest_os_info["id"]:
                return guest_os_info["id"]

        # Fallback to annotation
        annotations = vmi_item.get("metadata", {}).get("annotations", {})
        os_annotation = annotations.get("vm.kubevirt.io/os")
        if os_annotation:
            return os_annotation

        return None

    def _extract_os_from_vm(self: "VMOSLookup", vm_item: Dict[str, Any]) -> Optional[str]:
        """Extract OS information from a VirtualMachine resource.

        Args:
            vm_item (Dict[str, Any]): A VM resource dictionary.

        Returns:
            Optional[str]: OS name/identifier, or None if not found.
        """
        # VMs might have guestOSInfo in status if they have a running VMI
        guest_os_info = vm_item.get("status", {}).get("guestOSInfo", {})
        if guest_os_info:
            if "prettyName" in guest_os_info and guest_os_info["prettyName"]:
                return guest_os_info["prettyName"]
            if "name" in guest_os_info and guest_os_info["name"]:
                os_name = guest_os_info["name"]
                if "version" in guest_os_info and guest_os_info["version"]:
                    os_name = f"{os_name} {guest_os_info['version']}"
                return os_name
            if "id" in guest_os_info and guest_os_info["id"]:
                return guest_os_info["id"]

        # Check annotation
        annotations = vm_item.get("metadata", {}).get("annotations", {})
        os_annotation = annotations.get("vm.kubevirt.io/os")
        if os_annotation:
            return os_annotation

        # Check preference name (e.g., "rhel.9")
        preference = vm_item.get("spec", {}).get("preference", {})
        if preference and "name" in preference:
            return preference["name"]

        return None

    def _load_yaml_file(self: "VMOSLookup", file_path: str) -> Optional[Dict[str, Any]]:
        """Load a YAML file and return its contents.

        Args:
            file_path (str): Path to the YAML file.

        Returns:
            Optional[Dict[str, Any]]: Parsed YAML content, or None if file doesn't exist or is invalid.
        """
        if not os.path.isfile(file_path):
            return None

        try:
            with open(file_path, "r") as yaml_file:
                return yaml.safe_load(yaml_file)
        except (yaml.YAMLError, IOError):
            return None

    def load_vm_yaml_files(self: "VMOSLookup") -> None:
        """Load all VMI/VM YAML files from vm_yaml directory and build OS lookup.

        Processes files containing:
        - VirtualMachineInstance resources (kind: VirtualMachineInstance)
        - VirtualMachine resources (kind: VirtualMachine)

        Builds a lookup dictionary mapping VM names to OS information.
        """
        if not os.path.isdir(self.vm_yaml_dir):
            return

        yaml_files = [
            f
            for f in os.listdir(self.vm_yaml_dir)
            if f.endswith((".yaml", ".yml")) and os.path.isfile(os.path.join(self.vm_yaml_dir, f))
        ]

        for file_name in yaml_files:
            file_path = os.path.join(self.vm_yaml_dir, file_name)
            yaml_data = self._load_yaml_file(file_path)

            if not yaml_data:
                continue

            # Handle both single items and lists with "items" key
            items = []
            if "items" in yaml_data:
                items = yaml_data["items"]
            elif isinstance(yaml_data, list):
                items = yaml_data
            elif yaml_data.get("kind") in ("VirtualMachineInstance", "VirtualMachine"):
                items = [yaml_data]

            # Process each item
            for item in items:
                if not isinstance(item, dict):
                    continue

                kind = item.get("kind")
                metadata = item.get("metadata", {})
                vm_name = metadata.get("name")

                if not vm_name:
                    continue

                os_info = None
                if kind == "VirtualMachineInstance":
                    os_info = self._extract_os_from_vmi(item)
                elif kind == "VirtualMachine":
                    os_info = self._extract_os_from_vm(item)

                # Only update if we found OS info and haven't seen this VM before
                # (VMI takes precedence over VM if both exist)
                if os_info and (vm_name not in self.os_lookup or kind == "VirtualMachineInstance"):
                    self.os_lookup[vm_name] = os_info

    def get_os_for_vm(self: "VMOSLookup", vm_name: str) -> Optional[str]:
        """Get OS information for a VM by name.

        Args:
            vm_name (str): Name of the VM.

        Returns:
            Optional[str]: OS name/identifier, or None if not found.
        """
        return self.os_lookup.get(vm_name)

    def get_lookup(self: "VMOSLookup") -> Dict[str, str]:
        """Get the complete OS lookup dictionary.

        Returns:
            Dict[str, str]: Dictionary mapping VM names to OS information.
        """
        return self.os_lookup.copy()


