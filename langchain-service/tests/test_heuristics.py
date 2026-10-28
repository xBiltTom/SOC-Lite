"""Cinco casos de evaluación de la heurística conservadora."""
import unittest

from app.engines.heuristics import heuristic
from app.models import AlertIn


class HeuristicCases(unittest.TestCase):
    def check_case(self, description, level, criticality, severity, expected, enrichment=None, hint=None):
        alert = AlertIn(description=description, rule_level=level, asset_criticality=criticality, severity=severity)
        result = heuristic(alert, enrichment or [], hint)
        self.assertEqual(result.verdict, expected)
        self.assertEqual(result.severity, severity)
        self.assertEqual(result.status, 'degraded')
        self.assertTrue(result.needs_human)
        self.assertTrue(result.fallback_used)
        self.assertIn('no está calibrada', result.reasoning)

    def test_brute_force_without_confirmation_is_suspicious(self):
        self.check_case('Fuerza bruta en activo crítico sin confirmación', 12, 5, 'critical', 'suspicious')

    def test_medium_alert_without_evidence_is_inconclusive(self):
        self.check_case('Actividad media sin evidencia suficiente', 7, 3, 'medium', 'inconclusive')

    def test_routine_event_without_confirmation_is_inconclusive(self):
        self.check_case('Evento rutinario sin validación humana', 2, 2, 'info', 'inconclusive')

    def test_bad_reputation_requires_investigation(self):
        self.check_case('Indicador negativo requiere investigación', 8, 3, 'medium', 'suspicious',
                        enrichment=[{'status': 'ok', 'verdict': 'malicious'}])

    def test_automatic_history_does_not_lower_risk(self):
        self.check_case('Resultados automáticos previos no reducen riesgo', 12, 5, 'critical', 'suspicious',
                        hint={'false_positives': 5})


if __name__ == '__main__':
    unittest.main()
