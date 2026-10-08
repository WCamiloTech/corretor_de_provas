
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
AVALIACAO = BASE / "avaliacao.json"
LEITURA = BASE / "resultados" / "resultado_leitura.json"
SAIDA = BASE / "resultados" / "resultado_correcao.json"


def carregar_json(caminho):
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def solicitar_nota(numero, maximo):
    while True:
        entrada = input(
            f"Nota discursiva {numero} (0 a {maximo}, "
            "Enter = pendente): "
        ).strip()

        if not entrada:
            return None

        try:
            nota = float(entrada.replace(",", "."))
            if 0 <= nota <= maximo:
                return nota
        except ValueError:
            pass

        print("Nota inválida. Tente novamente.")


def revisar_resposta(numero, alternativas):
    print(f"\nQuestão {numero}: leitura incerta.")
    print("Alternativas:", ", ".join(alternativas))

    while True:
        entrada = input(
            "Resposta confirmada (A-E), "
            "B=branco, M=múltipla, "
            "Enter=manter pendente: "
        ).strip().upper()

        if entrada == "":
            return None, "pendente"

        if entrada == "B":
            return None, "em_branco"

        if entrada == "M":
            return None, "multipla"

        if entrada in alternativas:
            return entrada, "revisada"

        print("Opção inválida.")


def main():
    avaliacao = carregar_json(AVALIACAO)
    leitura = carregar_json(LEITURA)

    if avaliacao["id"] != leitura["avaliacao_id"]:
        raise ValueError("Avaliação incompatível com a leitura.")

    if avaliacao["aluno"]["id"] != leitura["aluno_id"]:
        raise ValueError("Aluno incompatível com a leitura.")

    resultados = []
    pontos_obtidos = 0.0
    pontos_possiveis = 0.0
    pendencias = []

    print("\nCORREÇÃO DA AVALIAÇÃO")
    print("-" * 40)
    print("Aluno:", avaliacao["aluno"]["nome"])

    for questao in avaliacao["questoes"]:
        numero = questao["numero"]
        tipo = questao["tipo"]
        pontos = float(questao["pontos"])

        pontos_possiveis += pontos

        if tipo == "objetiva":
            item = leitura["respostas"].get(str(numero))

            if item is None:
                raise ValueError(
                    f"Questão {numero} não encontrada na leitura."
                )

            resposta = item["resposta"]
            status = item["status"]

            if status == "incerta":
                resposta, status = revisar_resposta(
                    numero, questao["alternativas"]
                )

            elif status not in (
                "marcada", "em_branco", "multipla"
            ):
                raise ValueError(
                    f"Status desconhecido na questão {numero}."
                )

            if status == "pendente":
                pendencias.append(numero)
                nota = None
            else:
                nota = (
                    pontos
                    if resposta == questao["gabarito"]
                    else 0.0
                )
                pontos_obtidos += nota

            resultados.append({
                "numero": numero,
                "tipo": tipo,
                "resposta": resposta,
                "gabarito": questao["gabarito"],
                "status": status,
                "pontos_possiveis": pontos,
                "pontos_obtidos": nota
            })

        elif tipo == "discursiva":
            nota = solicitar_nota(numero, pontos)

            if nota is None:
                pendencias.append(numero)
                status = "pendente"
            else:
                pontos_obtidos += nota
                status = "corrigida"

            resultados.append({
                "numero": numero,
                "tipo": tipo,
                "status": status,
                "pontos_possiveis": pontos,
                "pontos_obtidos": nota
            })

        else:
            raise ValueError(
                f"Tipo de questão desconhecido: {tipo}"
            )

    finalizada = len(pendencias) == 0

    resultado = {
        "avaliacao_id": avaliacao["id"],
        "cartao_id": leitura["cartao_id"],
        "aluno_id": avaliacao["aluno"]["id"],
        "aluno_nome": avaliacao["aluno"]["nome"],
        "questoes": resultados,
        "pontos_possiveis": pontos_possiveis,
        "pontos_confirmados": pontos_obtidos,
        "nota_final": (
            pontos_obtidos if finalizada else None
        ),
        "status": (
            "finalizada" if finalizada else "pendente"
        ),
        "pendencias": pendencias
    }

    SAIDA.parent.mkdir(parents=True, exist_ok=True)

    with SAIDA.open("w", encoding="utf-8") as arquivo:
        json.dump(
            resultado,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    print("\nRESULTADO")
    print("-" * 40)
    print(f"Pontos confirmados: {pontos_obtidos:g}")
    print(f"Pontuação máxima: {pontos_possiveis:g}")
    print(f"Situação: {resultado['status']}")

    if finalizada:
        print(f"Nota final: {pontos_obtidos:g}")
    else:
        print("Nota final: pendente")
        print("Questões pendentes:", pendencias)

    print("\nArquivo gerado:", SAIDA)


if __name__ == "__main__":
    main()
