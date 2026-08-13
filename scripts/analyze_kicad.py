#!/usr/bin/env python3
"""Extrahiert Matrix- und Bauteildaten aus KiCad-Dateien."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterator, Union


SExpression = Union[str, list["SExpression"]]


def tokenize(source: str) -> Iterator[str]:
    """Zerlegt KiCad-S-Expressions ohne externe Abhängigkeiten."""
    token_pattern = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
    yield from token_pattern.findall(source)


def parse(source: str) -> SExpression:
    """Liest genau eine vollständige S-Expression."""
    stack: list[list[SExpression]] = []
    root: SExpression | None = None

    for token in tokenize(source):
        if token == "(":
            node: list[SExpression] = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
        elif token == ")":
            if not stack:
                raise ValueError("Unerwartete schließende Klammer")
            root = stack.pop()
        else:
            if not stack:
                raise ValueError("Atom außerhalb einer S-Expression")
            if token.startswith('"'):
                token = json.loads(token)
            stack[-1].append(token)

    if stack:
        raise ValueError("Nicht geschlossene S-Expression")
    if root is None:
        raise ValueError("Leere Eingabe")
    return root


def children(node: SExpression, name: str) -> Iterator[list[SExpression]]:
    """Liefert direkte Kindlisten mit dem angegebenen Namen."""
    if not isinstance(node, list):
        return
    for child in node:
        if isinstance(child, list) and child and child[0] == name:
            yield child


def first_child(node: SExpression, name: str) -> list[SExpression] | None:
    """Liefert das erste passende direkte Kind."""
    return next(children(node, name), None)


def property_value(node: SExpression, name: str) -> str | None:
    """Liest den Wert einer KiCad-Eigenschaft."""
    for item in children(node, "property"):
        if len(item) >= 3 and item[1] == name:
            return str(item[2])
    return None


def footprint_summary(footprint: list[SExpression]) -> dict[str, object]:
    """Verdichtet die für die Matrixanalyse relevanten Footprint-Daten."""
    location = first_child(footprint, "at") or []
    pads: dict[str, dict[str, set[str]]] = {}

    for pad in children(footprint, "pad"):
        if len(pad) < 2:
            continue
        pad_number = str(pad[1])
        pad_data = pads.setdefault(
            pad_number,
            {"nets": set(), "functions": set(), "positions": set()},
        )
        net = first_child(pad, "net")
        if net and len(net) >= 3:
            pad_data["nets"].add(str(net[2]))
        pin_function = first_child(pad, "pinfunction")
        if pin_function and len(pin_function) >= 2:
            pad_data["functions"].add(str(pin_function[1]))
        pad_location = first_child(pad, "at")
        if pad_location and len(pad_location) >= 3:
            pad_data["positions"].add(" ".join(str(value) for value in pad_location[1:4]))

    return {
        "reference": property_value(footprint, "Reference"),
        "value": property_value(footprint, "Value"),
        "library": footprint[1] if len(footprint) > 1 else None,
        "at": [str(value) for value in location[1:4]],
        "pads": {
            key: {field: sorted(values) for field, values in value.items()}
            for key, value in sorted(pads.items())
        },
    }


def pad_instances(footprint: list[SExpression]) -> list[dict[str, object]]:
    """Liefert jede nummerierte Pad-Instanz samt Lage und Kupferseite."""
    result: list[dict[str, object]] = []
    for pad in children(footprint, "pad"):
        if len(pad) < 2 or not str(pad[1]):
            continue
        location = first_child(pad, "at") or []
        layers = first_child(pad, "layers") or []
        net = first_child(pad, "net") or []
        pin_function = first_child(pad, "pinfunction") or []
        result.append(
            {
                "number": str(pad[1]),
                "type": str(pad[2]) if len(pad) > 2 else "",
                "shape": str(pad[3]) if len(pad) > 3 else "",
                "at": [str(value) for value in location[1:4]],
                "layers": [str(value) for value in layers[1:]],
                "net": str(net[2]) if len(net) >= 3 else "",
                "function": str(pin_function[1]) if len(pin_function) >= 2 else "",
            }
        )
    return result


def schematic_summary(schematic: list[SExpression]) -> dict[str, object]:
    """Fasst Bauteile und globale Netznamen eines Schaltplans zusammen."""
    symbols: list[dict[str, object]] = []
    for symbol in children(schematic, "symbol"):
        location = first_child(symbol, "at") or []
        library_id = first_child(symbol, "lib_id") or []
        symbols.append(
            {
                "reference": property_value(symbol, "Reference"),
                "value": property_value(symbol, "Value"),
                "library_id": str(library_id[1]) if len(library_id) >= 2 else "",
                "at": [str(value) for value in location[1:4]],
            }
        )

    labels: list[dict[str, object]] = []
    for label in children(schematic, "global_label"):
        location = first_child(label, "at") or []
        labels.append(
            {
                "name": str(label[1]) if len(label) >= 2 else "",
                "at": [str(value) for value in location[1:4]],
            }
        )

    symbols.sort(key=lambda item: str(item["reference"]))
    labels.sort(key=lambda item: (str(item["name"]), item["at"]))
    return {"symbols": symbols, "global_labels": labels}


def main() -> None:
    """Gibt alle Schalter und den Controller als JSON aus."""
    parser = argparse.ArgumentParser()
    parser.add_argument("pcb", type=Path)
    parser.add_argument("--controller-pads", action="store_true")
    args = parser.parse_args()

    document = parse(args.pcb.read_text(encoding="utf-8"))
    if not isinstance(document, list) or not document:
        raise ValueError("Die Datei enthält keine KiCad-S-Expression")

    if document[0] == "kicad_sch":
        print(json.dumps(schematic_summary(document), indent=2, ensure_ascii=False))
        return
    if document[0] != "kicad_pcb":
        raise ValueError("Die Datei ist weder KiCad-PCB noch KiCad-Schaltplan")

    footprint_nodes = list(children(document, "footprint"))
    if args.controller_pads:
        controller = next(
            item for item in footprint_nodes if property_value(item, "Reference") == "U1"
        )
        print(json.dumps(pad_instances(controller), indent=2, ensure_ascii=False))
        return

    footprints = [footprint_summary(item) for item in footprint_nodes]
    relevant = [
        item
        for item in footprints
        if str(item["reference"]).startswith("S") or item["reference"] == "U1"
    ]
    relevant.sort(
        key=lambda item: (
            0 if item["reference"] == "U1" else 1,
            int(str(item["reference"])[1:]) if str(item["reference"]).startswith("S") else 0,
        )
    )
    print(json.dumps(relevant, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
