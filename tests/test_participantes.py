
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gerenciar_participantes as gp


class TestGerenciamentoParticipantes(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.base = Path(self.temp.name)
        self.resultados = self.base / "resultados"

        self.avaliacao = {
            "id": "MMC2-TESTE-AV01",
            "turma": "MMC2",
            "titulo": "Avaliação de Teste",
            "questoes": []
        }

        self.cadastro = {
            "turma": "MMC2",
            "alunos": [
                {
                    "id": "ALUNO-001",
                    "nome": "Aluno Teste 01",
                    "ativo": True
                },
                {
                    "id": "ALUNO-002",
                    "nome": "Aluno Teste 02",
                    "ativo": True
                },
                {
                    "id": "ALUNO-003",
                    "nome": "Aluno Teste 03",
                    "ativo": True
                },
                {
                    "id": "ALUNO-004",
                    "nome": "Aluno Teste 04",
                    "ativo": False
                }
            ]
        }

        self.arq_avaliacao = (
            self.base / "avaliacao.json"
        )

        self.arq_alunos = (
            self.base / "alunos.json"
        )

        self.arq_avaliacao.write_text(
            json.dumps(self.avaliacao),
            encoding="utf-8"
        )

        self.arq_alunos.write_text(
            json.dumps(self.cadastro),
            encoding="utf-8"
        )

        self.patches = [
            patch.object(
                gp, "BASE", self.base
            ),
            patch.object(
                gp, "ARQ_AVALIACAO",
                self.arq_avaliacao
            ),
            patch.object(
                gp, "ARQ_ALUNOS",
                self.arq_alunos
            ),
            patch.object(
                gp, "PASTA_RESULTADOS",
                self.resultados
            )
        ]

        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def executar_com_entradas(self, funcao, entradas):
        saida = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=entradas
        ):
            with contextlib.redirect_stdout(saida):
                funcao()

        return saida.getvalue()

    def destino(self):
        return (
            self.resultados
            / self.avaliacao["id"]
            / "participantes.json"
        )

    def criar_registro_teste(self):
        self.executar_com_entradas(
            lambda: gp.criar_registro(
                self.avaliacao,
                self.cadastro
            ),
            [
                "ALUNO-001,ALUNO-002,ALUNO-003",
                "S"
            ]
        )

    def test_listar_alunos(self):
        saida = self.executar_com_entradas(
            lambda: gp.listar_alunos(
                self.cadastro
            ),
            []
        )

        self.assertIn("ALUNO-001", saida)
        self.assertIn("ALUNO-004", saida)
        self.assertIn("Inativo", saida)

    def test_registro_inexistente(self):
        saida = self.executar_com_entradas(
            lambda: gp.consultar_registro(
                self.avaliacao,
                self.cadastro
            ),
            []
        )

        self.assertIn(
            "Ainda não existe registro",
            saida
        )

    def test_criar_participantes(self):
        self.criar_registro_teste()

        self.assertTrue(
            self.destino().is_file()
        )

        dados = json.loads(
            self.destino().read_text(
                encoding="utf-8"
            )
        )

        ids = [
            p["aluno_id"]
            for p in dados["participantes"]
        ]

        self.assertEqual(
            ids,
            [
                "ALUNO-001",
                "ALUNO-002",
                "ALUNO-003"
            ]
        )

        self.assertNotIn(
            "ALUNO-004",
            ids
        )

    def test_consultar_participantes(self):
        self.criar_registro_teste()

        saida = self.executar_com_entradas(
            lambda: gp.consultar_registro(
                self.avaliacao,
                self.cadastro
            ),
            []
        )

        self.assertIn(
            "Total: 3",
            saida
        )

        self.assertIn(
            "ALUNO-003",
            saida
        )

    def test_impedir_sobrescrita(self):
        self.criar_registro_teste()

        conteudo_original = (
            self.destino().read_bytes()
        )

        saida = self.executar_com_entradas(
            lambda: gp.criar_registro(
                self.avaliacao,
                self.cadastro
            ),
            []
        )

        self.assertIn(
            "já existe",
            saida
        )

        self.assertEqual(
            self.destino().read_bytes(),
            conteudo_original
        )

    def test_rejeitar_id_duplicado(self):
        saida = self.executar_com_entradas(
            lambda: gp.criar_registro(
                self.avaliacao,
                self.cadastro
            ),
            [
                "ALUNO-001,ALUNO-001"
            ]
        )

        self.assertIn(
            "IDs repetidos",
            saida
        )

        self.assertFalse(
            self.destino().exists()
        )

    def test_rejeitar_aluno_inexistente(self):
        saida = self.executar_com_entradas(
            lambda: gp.criar_registro(
                self.avaliacao,
                self.cadastro
            ),
            [
                "ALUNO-999"
            ]
        )

        self.assertIn(
            "IDs não encontrados",
            saida
        )

        self.assertFalse(
            self.destino().exists()
        )

    def test_preservar_arquivos(self):
        pasta_aluno = (
            self.resultados
            / self.avaliacao["id"]
            / "ALUNO-001"
        )

        pasta_aluno.mkdir(
            parents=True
        )

        arquivo_historico = (
            pasta_aluno
            / "resultado_correcao.json"
        )

        conteudo = b'{"teste": "preservado"}'

        arquivo_historico.write_bytes(
            conteudo
        )

        self.criar_registro_teste()

        self.assertEqual(
            arquivo_historico.read_bytes(),
            conteudo
        )


if __name__ == "__main__":
    unittest.main()
