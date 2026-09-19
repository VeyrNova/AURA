import unittest

from ui.text_rendering import normalize_markdown_math, normalize_markdown_text, normalize_plain_text


class Patch2688ResponseMathSanitizerTests(unittest.TestCase):
    def test_gemini_arrow_is_rendered_as_unicode(self):
        src = r"Un réarmement a été effectué $\rightarrow$ aucun code erreur après réarmement."
        out = normalize_markdown_text(src)
        self.assertEqual(out, "Un réarmement a été effectué → aucun code erreur après réarmement.")
        self.assertNotIn("\\rightarrow", out)
        self.assertNotIn("$", out)

    def test_simple_comparison_math_is_readable(self):
        out = normalize_markdown_text(r"Alerte si $T \geq 30$ et $P \neq 0$.")
        self.assertEqual(out, "Alerte si T ≥ 30 et P ≠ 0.")

    def test_display_math_is_unwrapped(self):
        out = normalize_markdown_text("Résultat:\n$$A \\Rightarrow B$$\nSuite")
        self.assertEqual(out, "Résultat:\nA ⇒ B\nSuite")

    def test_common_text_wrapper_is_unwrapped(self):
        self.assertEqual(normalize_markdown_text(r"Valeur $\text{OK}$"), "Valeur OK")

    def test_currency_dollar_is_not_removed(self):
        out = normalize_markdown_text("Budget indicatif : 10 $ par mois")
        self.assertEqual(out, "Budget indicatif : 10 $ par mois")

    def test_markdown_formatting_is_preserved(self):
        src = "**Important**\n\n- état : `OK`\n- transition : $\\rightarrow$ terminée"
        out = normalize_markdown_text(src)
        self.assertIn("**Important**", out)
        self.assertIn("`OK`", out)
        self.assertIn("→ terminée", out)

    def test_plain_text_uses_same_math_cleanup(self):
        out = normalize_plain_text(r"<b>Action</b> $\rightarrow$ terminée")
        self.assertEqual(out, "Action → terminée")

    def test_unknown_backslash_command_is_not_destroyed(self):
        src = r"Commande technique \customcmd sans math"
        self.assertEqual(normalize_markdown_math(src), src)


if __name__ == "__main__":
    unittest.main()
