"""Guardrail gates ported from assets/chatbot.js.

Pipeline order (preserved exactly — see gates.py docstring for why the order
itself is part of the contract):

    sanitise -> injection -> task_request -> route -> personal
      -> retrieve -> unknown-subject deflect check -> fit-question path
      -> scope -> evidence -> (generate) -> citation validation
"""
