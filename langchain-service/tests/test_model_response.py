"""Validación de respuestas compatibles con el contrato del triaje."""
import unittest

from app.agents.triage_agent import LLMDecision


class ModelResponseTests(unittest.TestCase):
    def test_fifth_action_priority_is_normalized(self):
        decision = LLMDecision.model_validate({
            "verdict": "suspicious", "severity": "high", "confidence": 0.6,
            "summary": "Revisar la alerta con un analista", "recommended_actions": [
                {"action": "Revisar evidencia", "priority": 5, "owner": "SOC"}
            ],
        })
        self.assertEqual(decision.recommended_actions[0].priority, 4)


if __name__ == "__main__":
    unittest.main()
