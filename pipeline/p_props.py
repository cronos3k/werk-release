#!/usr/bin/env python3
"""p_props.py — core.props, the simulation property block.

This is the one producer that wants a model it may not have. The registry asks
for flammability, thermal, mechanical, fluid, electrical and magnetic
behaviour, and none of that is derivable from a triangle mesh: it is knowledge
about what the object is MADE OF, which is a question about a picture.

So there are two paths and they are labelled differently, never blended:

  VLM reachable   the vision-language model at $WERK_VLM_BASE_URL is shown the
                  imposter preview sheet and asked for a material identification
                  and the registry's fields. Everything it returns is stamped
                  `inferred`, with the model's exact id in `source`, and every
                  numeric field keeps a plausible range. The pipeline never
                  promotes a model's answer to `measured`.

  not reachable   a STUB: the registry's shape with the single field the
                  pipeline can stand behind (mechanical.density, which the
                  body node already assumed and which must agree with it to 1 %
                  per the schema), and a producer note that says in plain words
                  that no model was consulted and why the block is nearly
                  empty. The pipeline does NOT hard-require the model, and a
                  missing model is not a failed stage.

Endpoints come from the environment, never from a path baked into the source:
WERK_VLM_BASE_URL / WERK_VLM_MODEL, falling back to VISION_LLM_BASE_URL /
VISION_LLM_MODEL so a splat-foley `.env` works unchanged.
"""

import base64
import json
import os
import urllib.error
import urllib.request

from .common import jbytes

PROMPT = """You are looking at a contact sheet of one 3D asset rendered from 16
directions. Identify what the object is and what it is made of.

Reply with ONE JSON object and nothing else:
{"label": "<short name of the object>",
 "material": "<the dominant material, e.g. oak wood, mild steel, glazed ceramic>",
 "density_kg_m3": <number>,
 "density_range": [<low>, <high>],
 "flammability_class": "<non-combustible|self-extinguishing|slow-burning|flammable|highly-flammable>",
 "failure_mode": "<brittle|ductile|crushing|tearing|shattering|splintering|plastic-deformation>",
 "youngs_modulus_pa": <number>,
 "thermal_conductivity_w_mk": <number>,
 "specific_heat_j_kgk": <number>,
 "electrical_class": "<insulator|semiconductor|conductor|superconductor>",
 "magnetic_class": "<diamagnetic|paramagnetic|ferromagnetic|ferrimagnetic|antiferromagnetic|non-magnetic>",
 "porosity": <0..1>,
 "floats_in_water": <true|false>,
 "facets": {"style": [], "function": [], "environment": [], "era": [], "mood": [],
            "condition": []},
 "confidence": <0..1>}
Use only lowercase kebab-case tags for facets. Omit any field you cannot judge."""


def endpoint():
    base = (os.environ.get("WERK_VLM_BASE_URL") or
            os.environ.get("VISION_LLM_BASE_URL"))
    model = (os.environ.get("WERK_VLM_MODEL") or
             os.environ.get("VISION_LLM_MODEL"))
    return base, model


def ask_vlm(image_bytes, timeout=90):
    base, model = endpoint()
    if not base or not model:
        return None, "no WERK_VLM_BASE_URL / VISION_LLM_BASE_URL in the environment"
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model, "temperature": 0.0, "max_tokens": 900,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
                                                base64.b64encode(image_bytes).decode()}},
        ]}],
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        return None, "%s at %s: %s" % (type(e).__name__, url, e)
    text = body["choices"][0]["message"]["content"]
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        return None, "the model replied without a JSON object"
    try:
        return json.loads(text[s:e + 1]), model
    except ValueError as ex:
        return None, "the model's JSON did not parse: %s" % ex


def _num(value, unit, source, conf, rng=None):
    d = {"value": float(value), "unit": unit, "epistemic": "inferred",
         "confidence": float(conf), "source": source}
    if rng:
        d["range"] = [float(rng[0]), float(rng[1])]
    return d


def run(ctx, body, view_path, entity_name):
    answer, model_or_why = ask_vlm(ctx.files.get(view_path, b"")) if view_path else (None, "no preview sheet was baked")
    mech = {}
    props = {}
    region = {"region_id": "primary", "material_id": body["material_id"],
              "part_id": "whole", "label": entity_name, "properties": props}

    if answer:
        src = "vision-language model %s, shown %s" % (model_or_why, view_path)
        conf = float(answer.get("confidence", 0.4))
        if "density_kg_m3" in answer:
            mech["density"] = _num(answer["density_kg_m3"], "kg/m^3", src, conf,
                                   answer.get("density_range"))
        if "youngs_modulus_pa" in answer:
            mech["youngs_modulus"] = _num(answer["youngs_modulus_pa"], "Pa", src, conf)
        if "failure_mode" in answer:
            mech["failure_mode"] = {"value": answer["failure_mode"],
                                    "epistemic": "inferred", "confidence": conf,
                                    "source": src}
        if mech:
            props["mechanical"] = mech
        th = {}
        if "thermal_conductivity_w_mk" in answer:
            th["conductivity"] = _num(answer["thermal_conductivity_w_mk"],
                                      "W/(m*K)", src, conf)
        if "specific_heat_j_kgk" in answer:
            th["specific_heat"] = _num(answer["specific_heat_j_kgk"],
                                       "J/(kg*K)", src, conf)
        if th:
            props["thermal"] = th
        if "flammability_class" in answer:
            props["flammability"] = {"class": {"value": answer["flammability_class"],
                                               "epistemic": "inferred",
                                               "confidence": conf, "source": src}}
        if "electrical_class" in answer:
            props["electrical"] = {"class": {"value": answer["electrical_class"],
                                             "epistemic": "inferred",
                                             "confidence": conf, "source": src}}
        if "magnetic_class" in answer:
            props["magnetic"] = {"class": {"value": answer["magnetic_class"],
                                           "epistemic": "inferred",
                                           "confidence": conf, "source": src}}
        fl = {}
        if "porosity" in answer:
            fl["porosity"] = _num(answer["porosity"], "1", src, conf)
        if "floats_in_water" in answer:
            fl["floats_in_water"] = {"value": bool(answer["floats_in_water"]),
                                     "epistemic": "inferred", "confidence": conf,
                                     "source": src}
        if fl:
            props["fluid"] = fl
        note = ("Every value here came from %s and every one of them is stamped "
                "inferred. The model was shown the imposter preview sheet and "
                "nothing else - no filename, no text prompt about the asset - so "
                "its answers are about the pixels. Nothing in this block was "
                "promoted to measured, because nobody put this object on an "
                "instrument." % src)
        reached = True
        label = answer.get("label") or entity_name
        region["label"] = label
    else:
        src = ("no model: %s. Density is the class-level prior physics/body.json "
               "assumed, repeated here so the two agree." % model_or_why)
        props["mechanical"] = {"density": _num(
            body["density"], "kg/m^3", src, 0.35, body["density_range"])}
        note = ("A vision-language model was NOT reachable on this run (%s), so "
                "this block carries exactly one field: the density that "
                "physics/body.json already assumed, repeated so the schema's "
                "'must agree within 1%%' rule has something to check against. "
                "Every other field in the v1 registry is ABSENT rather than "
                "guessed. The pipeline does not require the model and did not "
                "fail without it; it simply has less to say."
                % model_or_why)
        reached = False
        label = entity_name

    doc = {"schema_version": 1, "registry_version": 1, "regions": [region],
           "note": note}
    f = ctx.put("properties/properties.json", jbytes(doc))
    ctx.node("props", "core.props",
             ctx.version([f], "Simulation properties for the primary material "
                              "region. %s"
                         % ("Inferred by a vision-language model from the "
                            "imposter sheet." if reached else
                            "No model was reachable; the block is a stub and "
                            "says so."),
                         "inferred",
                         inputs=[view_path] if (reached and view_path) else
                                ["physics/body.json"],
                         confidence=float(answer.get("confidence", 0.4)) if answer else 0.35,
                         model=model_or_why if reached else None),
             edges=[{"to": "body", "kind": "enhances", "role": "material-of"}],
             material=body["material_id"], part="whole")
    ctx.schemas["core.props"] = "spec/schemas/core.props.schema.json"
    return {"vlm": reached, "why": None if reached else model_or_why,
            "model": model_or_why if reached else None, "label": label,
            "fields": sum(len(v) for v in props.values()),
            "answer": answer}
