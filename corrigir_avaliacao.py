import json
import shutil
from datetime import datetime
from pathlib import Path
import copy

BASE = Path(__file__).resolve().parent
AVALIACAO = BASE / "avaliacao.json"
LEITURA = BASE / "resultados" / "resultado_leitura.json"
SAIDA = BASE / "resultados" / "resultado_correcao.json"
HISTORICO = BASE / "resultados" / "historico"

HISTORICO.mkdir(parents=True, exist_ok=True)


def carregar(caminho):
    with caminho.open("r", encoding="utf-8") as f:
        return json.load(f)


def salvar(dados):
    SAIDA.parent.mkdir(parents=True, exist_ok=True)

    # Salva primeiro em arquivo temporário.
    temporario = SAIDA.with_suffix(".tmp")

    with temporario.open("w", encoding="utf-8") as f:
        json.dump(
            dados, f, ensure_ascii=False, indent=2
        )

    temporario.replace(SAIDA)


def criar_backup():
    if not SAIDA.exists():
        return

    agora = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    destino = HISTORICO / f"correcao_{agora}.json"
    shutil.copy2(SAIDA, destino)


def solicitar_nota(numero, maximo):
    while True:
        entrada = input(
            f"Nota da questão {numero} "
            f"(0 a {maximo:g}, Enter = pendente): "
        ).strip()

        if not entrada:
            return None

        try:
            nota = float(entrada.replace(",", "."))
            if 0 <= nota <= maximo:
                return round(nota, 2)
        except ValueError:
            pass

        print("Nota inválida.")


def revisar_resposta(numero, alternativas):
    print(f"\nRevisão da questão {numero}")

    while True:
        entrada = input(
            "Alternativa A-E, "
            "0 = em branco, "
            "M = múltipla, "
            "Enter = pendente: "
        ).strip().upper()

        if entrada == "":
            return None, "pendente"

        if entrada == "0":
            return None, "em_branco"

        if entrada == "M":
            return None, "multipla"

        if entrada in alternativas:
            return entrada, "revisada"

        print("Opção inválida.")


def criar_resultado_inicial(avaliacao, leitura):
    questoes = []

    for q in avaliacao["questoes"]:
        numero = q["numero"]
        tipo = q["tipo"]

        item = {
            "numero": numero,
            "tipo": tipo,
            "pontos_possiveis": float(q["pontos"]),
            "pontos_obtidos": None
        }

        if tipo == "objetiva":
            leitura_q = leitura["respostas"].get(
                str(numero)
            )

            if leitura_q is None:
                raise ValueError(
                    f"Leitura ausente: questão {numero}"
                )

            item.update({
                "resposta": leitura_q["resposta"],
                "gabarito": q["gabarito"],
                "status": leitura_q["status"]
            })

        elif tipo == "discursiva":
            item["status"] = "pendente"

        else:
            raise ValueError(
                f"Tipo desconhecido: {tipo}"
            )

        questoes.append(item)

    return {
        "avaliacao_id": avaliacao["id"],
        "cartao_id": leitura["cartao_id"],
        "aluno_id": avaliacao["aluno"]["id"],
        "aluno_nome": avaliacao["aluno"]["nome"],
        "questoes": questoes,
        "pontos_possiveis": 0,
        "pontos_confirmados": 0,
        "nota_final": None,
        "status": "pendente",
        "pendencias": []
    }


def atualizar_pontuacao(resultado):
    total = 0.0
    confirmados = 0.0
    pendencias = []

    for q in resultado["questoes"]:
        total += q["pontos_possiveis"]

        if q["status"] == "pendente":
            q["pontos_obtidos"] = None
            pendencias.append(q["numero"])
            continue

        if q["tipo"] == "objetiva":
            if q["status"] == "incerta":
                q["pontos_obtidos"] = None
                pendencias.append(q["numero"])
                continue

            q["pontos_obtidos"] = (
                q["pontos_possiveis"]
                if q["resposta"] == q["gabarito"]
                else 0.0
            )

        if q["pontos_obtidos"] is None:
            pendencias.append(q["numero"])
        else:
            confirmados += q["pontos_obtidos"]

    resultado["pontos_possiveis"] = round(total, 2)
    resultado["pontos_confirmados"] = round(
        confirmados, 2
    )
    resultado["pendencias"] = pendencias
    resultado["status"] = (
        "pendente" if pendencias else "finalizada"
    )
    resultado["nota_final"] = (
        None if pendencias else round(confirmados, 2)
    )


def corrigir_questao(q, definicao):
    numero = q["numero"]

    if q["tipo"] == "discursiva":
        nota = solicitar_nota(
            numero, q["pontos_possiveis"]
        )

        q["pontos_obtidos"] = nota
        q["status"] = (
            "corrigida" if nota is not None
            else "pendente"
        )

    else:
        resposta, status = revisar_resposta(
            numero, definicao["alternativas"]
        )

        q["resposta"] = resposta
        q["status"] = status


def mostrar_resumo(resultado):
    print("\nRESUMO DA CORREÇÃO")
    print("-" * 40)

    for q in resultado["questoes"]:
        nota = q["pontos_obtidos"]

        print(
            f"Q{q['numero']:02d} | "
            f"{q['status']:12} | "
            f"{'-' if nota is None else nota:g}"
            if nota is not None else
            f"Q{q['numero']:02d} | "
            f"{q['status']:12} | -"
        )

    print("-" * 40)
    print(
        "Pontos confirmados:",
        resultado["pontos_confirmados"]
    )
    print(
        "Pontuação máxima:",
        resultado["pontos_possiveis"]
    )
    print("Situação:", resultado["status"])
    print("Pendências:", resultado["pendencias"])
    print("Nota final:", resultado["nota_final"])


def main():
    avaliacao = carregar(AVALIACAO)
    leitura = carregar(LEITURA)

    if avaliacao["id"] != leitura["avaliacao_id"]:
        raise ValueError("Avaliação incompatível.")

    if (
        avaliacao["aluno"]["id"]
        != leitura["aluno_id"]
    ):
        raise ValueError("Aluno incompatível.")

    if SAIDA.exists():
        resultado = carregar(SAIDA)        

        if (
            resultado["avaliacao_id"] != avaliacao["id"]
            or resultado["aluno_id"]
            != avaliacao["aluno"]["id"]
            or resultado["cartao_id"]
            != leitura["cartao_id"]
        ):
            raise ValueError(
                "Correção existente pertence "
                "a outro cartão."
            )

        print("Correção anterior encontrada.")
    else:
        resultado = criar_resultado_inicial(
            avaliacao, leitura
        )
        print("Nova correção iniciada.")

# Guarda o estado antes de qualquer modificação.
    estado_anterior = (
    copy.deepcopy(resultado)
    if SAIDA.exists()
    else None
    )
    
    definicoes = {
        q["numero"]: q
        for q in avaliacao["questoes"]
    }

    atualizar_pontuacao(resultado)

    # Retoma apenas questões pendentes.
    for q in resultado["questoes"]:
        if q["status"] in ("pendente", "incerta"):
            corrigir_questao(
                q, definicoes[q["numero"]]
            )

    atualizar_pontuacao(resultado)
    mostrar_resumo(resultado)

    while True:
        entrada = input(
            "\nRevisar questão? "
            "(número ou Enter para finalizar): "
        ).strip()

        if not entrada:
            break

        if not entrada.isdigit():
            print("Informe o número da questão.")
            continue

        numero = int(entrada)

        item = next(
            (
                q for q in resultado["questoes"]
                if q["numero"] == numero
            ),
            None
        )

        if item is None:
            print("Questão não encontrada.")
            continue

        corrigir_questao(
            item, definicoes[numero]
        )

        atualizar_pontuacao(resultado)
        mostrar_resumo(resultado)

    # criar_backup()
    # salvar(resultado)
    # if resultado != estado_anterior:
    #     criar_backup()
    #     salvar(resultado)
    #     print("\nAlterações salvas com sucesso.")
    # else:
    #     print("\nNenhuma alteração realizada.")
    #     print("O histórico foi preservado.")

    # print("\nCorreção salva em:", SAIDA)
    if estado_anterior is None:
        salvar(resultado)
        print("\nNova correção salva com sucesso.")

    elif resultado != estado_anterior:
        criar_backup()
        salvar(resultado)
        print("\nAlterações salvas com sucesso.")

    else:
        print("\nNenhuma alteração realizada.")
        print("O histórico foi preservado.")

    print("\nArquivo de correção:", SAIDA)


if __name__ == "__main__":
    main()
