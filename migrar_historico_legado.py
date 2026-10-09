
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


# ============================================================
# CONFIGURAÇÕES — V0.6.5
# ============================================================

BASE = Path(__file__).resolve().parent

AVALIACAO = BASE / "avaliacao.json"
CADASTRO = BASE / "alunos.json"

RESULTADOS = BASE / "resultados"
HISTORICO_LEGADO = RESULTADOS / "historico"


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def carregar(caminho):
    with caminho.open(
        "r", encoding="utf-8"
    ) as arquivo:
        return json.load(arquivo)


def validar_id(valor):
    if (
        not isinstance(valor, str)
        or not re.fullmatch(
            r"[A-Za-z0-9_-]+", valor
        )
    ):
        raise ValueError(
            f"Identificador inválido: {valor}"
        )

    return valor


def hash_arquivo(caminho):
    digest = hashlib.sha256()

    with caminho.open("rb") as arquivo:
        for bloco in iter(
            lambda: arquivo.read(65536), b""
        ):
            digest.update(bloco)

    return digest.hexdigest()


def conteudo_equivalente(a, b):
    return carregar(a) == carregar(b)


def pasta_individual(avaliacao_id, aluno_id):
    return (
        RESULTADOS
        / validar_id(avaliacao_id)
        / validar_id(aluno_id)
    )


# ============================================================
# VALIDAÇÃO DE CADA BACKUP
# ============================================================

def validar_backup(
    dados,
    avaliacao,
    alunos_por_id
):
    avaliacao_id = avaliacao["id"]

    if dados.get("avaliacao_id") != avaliacao_id:
        raise ValueError(
            "Avaliação incompatível."
        )

    aluno_id = dados.get("aluno_id")

    if aluno_id not in alunos_por_id:
        raise ValueError(
            "Aluno não encontrado no cadastro."
        )

    aluno = alunos_por_id[aluno_id]

    if dados.get("aluno_nome") != aluno["nome"]:
        raise ValueError(
            "Nome do aluno incompatível."
        )

    cartao_esperado = str(
        uuid5(
            NAMESPACE_URL,
            f"{avaliacao_id}:{aluno_id}"
        )
    )

    if dados.get("cartao_id") != cartao_esperado:
        raise ValueError(
            "UUID do cartão incompatível."
        )

    questoes = dados.get("questoes")

    if not isinstance(questoes, list):
        raise ValueError(
            "Estrutura de questões inválida."
        )

    definicoes = {
        q["numero"]: q
        for q in avaliacao["questoes"]
    }

    numeros = [q.get("numero") for q in questoes]

    if (
        len(numeros) != len(definicoes)
        or set(numeros) != set(definicoes)
    ):
        raise ValueError(
            "Questões incompatíveis com a avaliação."
        )

    total = 0.0
    confirmados = 0.0
    pendencias = []

    for q in questoes:
        numero = q["numero"]
        definicao = definicoes[numero]

        if q.get("tipo") != definicao["tipo"]:
            raise ValueError(
                f"Tipo incompatível na questão {numero}."
            )

        maximo = float(definicao["pontos"])

        if abs(
            float(q["pontos_possiveis"]) - maximo
        ) > 0.001:
            raise ValueError(
                f"Pontuação máxima divergente na Q{numero}."
            )

        total += maximo

        status = q.get("status")
        pontos = q.get("pontos_obtidos")

        if status in ("pendente", "incerta"):
            if pontos is not None:
                raise ValueError(
                    f"Nota incompatível na Q{numero}."
                )

            pendencias.append(numero)
            continue

        if pontos is None:
            raise ValueError(
                f"Nota ausente na Q{numero}."
            )

        pontos = float(pontos)

        if not 0 <= pontos <= maximo:
            raise ValueError(
                f"Nota fora do intervalo na Q{numero}."
            )

        if q["tipo"] == "objetiva":
            if (
                q.get("gabarito")
                != definicao["gabarito"]
            ):
                raise ValueError(
                    f"Gabarito incompatível na Q{numero}."
                )

            resposta = q.get("resposta")

            if (
                resposta is not None
                and resposta not in definicao["alternativas"]
            ):
                raise ValueError(
                    f"Resposta inválida na Q{numero}."
                )

            if status not in (
                "marcada",
                "revisada",
                "em_branco",
                "multipla"
            ):
                raise ValueError(
                    f"Status inválido na Q{numero}."
                )

            if status in ("em_branco", "multipla"):
                if resposta is not None:
                    raise ValueError(
                        f"Resposta incompatível na Q{numero}."
                    )

            if status in ("marcada", "revisada"):
                if resposta not in definicao["alternativas"]:
                    raise ValueError(
                        f"Resposta ausente na Q{numero}."
                    )

            esperado = (
                maximo
                if resposta == definicao["gabarito"]
                else 0.0
            )

            if abs(pontos - esperado) > 0.001:
                raise ValueError(
                    f"Nota objetiva divergente na Q{numero}."
                )

        elif status != "corrigida":
            raise ValueError(
                f"Status discursivo inválido na Q{numero}."
            )

        confirmados += pontos

    if abs(
        float(dados["pontos_possiveis"]) - total
    ) > 0.001:
        raise ValueError(
            "Total de pontos possíveis divergente."
        )

    if abs(
        float(dados["pontos_confirmados"])
        - confirmados
    ) > 0.001:
        raise ValueError(
            "Pontos confirmados divergentes."
        )

    if set(dados.get("pendencias", [])) != set(
        pendencias
    ):
        raise ValueError(
            "Lista de pendências divergente."
        )

    status_esperado = (
        "pendente" if pendencias else "finalizada"
    )

    if dados.get("status") != status_esperado:
        raise ValueError(
            "Status geral incompatível."
        )

    if pendencias:
        if dados.get("nota_final") is not None:
            raise ValueError(
                "Correção pendente possui nota final."
            )
    else:
        if abs(
            float(dados["nota_final"])
            - confirmados
        ) > 0.001:
            raise ValueError(
                "Nota final divergente."
            )

    return aluno


# ============================================================
# PLANEJAMENTO DA MIGRAÇÃO
# ============================================================

def planejar_migracao():
    avaliacao = carregar(AVALIACAO)
    cadastro = carregar(CADASTRO)

    avaliacao_id = validar_id(avaliacao["id"])

    if cadastro.get("turma") != avaliacao.get("turma"):
        raise ValueError(
            "Turma incompatível."
        )

    alunos_por_id = {}

    for aluno in cadastro["alunos"]:
        aluno_id = validar_id(aluno["id"])

        if aluno_id in alunos_por_id:
            raise ValueError(
                f"Aluno duplicado: {aluno_id}"
            )

        alunos_por_id[aluno_id] = aluno

    if not HISTORICO_LEGADO.is_dir():
        raise FileNotFoundError(
            f"Histórico legado não encontrado: "
            f"{HISTORICO_LEGADO}"
        )

    arquivos = sorted(
        HISTORICO_LEGADO.glob("*.json")
    )

    planejamento = []
    hashes_reservados = {}

    for origem in arquivos:
        item = {
            "origem": origem,
            "destino": None,
            "aluno_id": None,
            "nota": None,
            "situacao": None,
            "motivo": ""
        }

        try:
            dados = carregar(origem)

            aluno = validar_backup(
                dados,
                avaliacao,
                alunos_por_id
            )

            aluno_id = aluno["id"]

            pasta = pasta_individual(
                avaliacao_id,
                aluno_id
            )

            correcao_atual = (
                pasta / "resultado_correcao.json"
            )

            if not correcao_atual.is_file():
                raise ValueError(
                    "Correção individual atual não encontrada."
                )

            atual = carregar(correcao_atual)

            if (
                atual.get("avaliacao_id") != avaliacao_id
                or atual.get("aluno_id") != aluno_id
                or atual.get("cartao_id")
                != dados.get("cartao_id")
            ):
                raise ValueError(
                    "Identificação da correção atual divergente."
                )

            destino_pasta = pasta / "historico"

            if not destino_pasta.is_dir():
                raise ValueError(
                    "Pasta de histórico individual não encontrada."
                )

            item["aluno_id"] = aluno_id
            item["nota"] = dados.get("nota_final")

            # Não duplica um backup que já esteja no destino.
            duplicado = False

            for existente in destino_pasta.glob("*.json"):
                if conteudo_equivalente(
                    origem, existente
                ):
                    duplicado = True
                    break

            if duplicado:
                item["situacao"] = "DUPLICADO"
                item["motivo"] = (
                    "Conteúdo já existe no histórico individual."
                )

                planejamento.append(item)
                continue

            hash_origem = hash_arquivo(origem)

            chave = (
                aluno_id,
                hash_origem
            )

            if chave in hashes_reservados:
                item["situacao"] = "DUPLICADO"
                item["motivo"] = (
                    "Arquivo idêntico já incluído "
                    "nesta migração."
                )

                planejamento.append(item)
                continue

            hashes_reservados[chave] = origem

            destino = destino_pasta / origem.name

            if destino.exists():
                # Preserva o nome original e acrescenta
                # um sufixo para evitar colisão.
                contador = 1

                while True:
                    destino = destino_pasta / (
                        f"{origem.stem}_legado_{contador}"
                        f"{origem.suffix}"
                    )

                    if not destino.exists():
                        break

                    contador += 1

            item["destino"] = destino
            item["situacao"] = "PRONTO"

        except (
            ValueError,
            KeyError,
            TypeError,
            OSError,
            json.JSONDecodeError
        ) as erro:
            item["situacao"] = "BLOQUEADO"
            item["motivo"] = str(erro)

        planejamento.append(item)

    return planejamento


# ============================================================
# EXIBIÇÃO DO PLANEJAMENTO
# ============================================================

def mostrar_planejamento(planejamento):
    print("\nANÁLISE DO HISTÓRICO LEGADO")
    print("=" * 65)

    for indice, item in enumerate(
        planejamento, start=1
    ):
        print(f"\n[{indice}] {item['origem'].name}")

        print("Situação:", item["situacao"])

        if item["aluno_id"]:
            print("Aluno:", item["aluno_id"])

        if item["nota"] is not None:
            print("Nota:", item["nota"])

        if item["destino"]:
            print("Destino:", item["destino"])

        if item["motivo"]:
            print("Observação:", item["motivo"])

    contagem = Counter(
        item["situacao"]
        for item in planejamento
    )

    print("\nRESUMO")
    print("-" * 65)
    print("Arquivos analisados:", len(planejamento))
    print("Prontos para copiar:", contagem["PRONTO"])
    print("Duplicados:", contagem["DUPLICADO"])
    print("Bloqueados:", contagem["BLOQUEADO"])

    return contagem


# ============================================================
# EXECUÇÃO SEGURA
# ============================================================

def executar_migracao(planejamento):
    copiados = 0
    falhas = 0

    for item in planejamento:
        if item["situacao"] != "PRONTO":
            continue

        origem = item["origem"]
        destino = item["destino"]

        try:
            # Nunca substitui um arquivo existente.
            with origem.open("rb") as fonte:
                with destino.open("xb") as saida:
                    shutil.copyfileobj(fonte, saida)

            if hash_arquivo(origem) != hash_arquivo(destino):
                raise ValueError(
                    "Falha na verificação da cópia."
                )

            print(
                f"[COPIADO] {origem.name} "
                f"-> {item['aluno_id']}"
            )

            copiados += 1

        except (
            OSError,
            ValueError
        ) as erro:
            print(
                f"[ERRO] {origem.name}: {erro}"
            )
            falhas += 1

    print("\nRESULTADO DA MIGRAÇÃO")
    print("-" * 65)
    print("Arquivos copiados:", copiados)
    print("Falhas:", falhas)
    print(
        "Os arquivos do histórico legado "
        "foram preservados."
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    print("\nMIGRAÇÃO DO HISTÓRICO LEGADO - V0.6.5")
    print("=" * 65)

    planejamento = planejar_migracao()

    if not planejamento:
        print(
            "\nNenhum arquivo JSON encontrado "
            "no histórico legado."
        )
        return

    contagem = mostrar_planejamento(
        planejamento
    )

    if contagem["BLOQUEADO"]:
        print(
            "\nExistem arquivos bloqueados. "
            "Nenhuma migração será executada."
        )
        return

    if not contagem["PRONTO"]:
        print(
            "\nNenhum arquivo novo precisa ser copiado."
        )
        return

    print(
        "\nSIMULAÇÃO CONCLUÍDA."
        "\nNenhum arquivo foi alterado."
    )

    confirmacao = input(
        "\nDigite MIGRAR para copiar os backups "
        "(Enter para cancelar): "
    ).strip()

    if confirmacao != "MIGRAR":
        print(
            "\nOperação cancelada. "
            "Nenhuma alteração realizada."
        )
        return

    executar_migracao(planejamento)


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        json.JSONDecodeError
    ) as erro:
        print(
            f"\nOperação interrompida: {erro}"
        )
