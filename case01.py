"""
Case 1 — Earnings Call Intelligence Tracker
Bradesco BBI — Estágio Tech/AI em Equity Strategy

Como usar:
    python tracker.py transcricao.txt
    python tracker.py transcricao.txt --output relatorio.md
"""

import json
import sys
import argparse
import os
from pathlib import Path
import google.generativeai as genai

# ── carrega o arquivo .env se existir ───────────────────────────────────────
env_path = Path(__file__).parent / "api.env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ── cliente da API ──────────────────────────────────────────────────────────
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction="""Você é um analista sênior de Equity Research especializado em
interpretar earnings calls de empresas brasileiras listadas no Ibovespa.

Suas análises são:
- Baseadas SOMENTE no texto da transcrição fornecida (nunca invente dados)
- Diretas e sem rodeios — analistas ocupados vão ler isso
- Com citações literais do texto quando pedido
- Honestas sobre o que NÃO é possível concluir com a informação disponível

Se alguma informação não puder ser extraída da transcrição, diga "Não identificado na transcrição"."""
)


# ── prompts ─────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """Analise a transcrição de earnings call abaixo e retorne um JSON com a estrutura exata pedida.

TRANSCRIÇÃO:
{transcricao}

Retorne APENAS o JSON abaixo, sem explicações, sem markdown, sem texto antes ou depois:

{{
  "empresa": "nome da empresa",
  "trimestre": "ex: 1T25",
  "tom_geral": {{
    "classificacao": "Positivo | Neutro | Negativo | Misto",
    "justificativa": "1-2 frases explicando",
    "trechos_de_suporte": [
      "trecho literal 1 da transcrição",
      "trecho literal 2 da transcrição"
    ]
  }},
  "guidance": {{
    "mudancas_identificadas": [
      {{
        "tema": "ex: receita, margem, capex",
        "descricao": "o que mudou vs trimestre anterior",
        "trecho_original": "citação literal"
      }}
    ],
    "temas_novos": ["tema 1", "tema 2"]
  }},
  "perguntas_analisas": [
    {{
      "pergunta_resumo": "resumo da pergunta do analista",
      "resposta_resumo": "resumo de como o CFO/CEO respondeu",
      "qualidade_resposta": "Boa | Evasiva | Incompleta | Excelente",
      "justificativa_qualidade": "por que essa classificação"
    }}
  ],
  "red_flags": [
    {{
      "tipo": "Hesitação | Evasão | Mudança de assunto | Linguagem vaga",
      "trecho_literal": "citação exata da transcrição",
      "contexto": "por que isso é um red flag"
    }}
  ],
  "surprise_score": {{
    "score": 1,
    "escala": "1 (sem surpresas) a 5 (muito surpreendente)",
    "justificativa": "por que esse score",
    "surpresas_identificadas": [
      {{
        "item": "o que foi surpreendente",
        "por_que_surpresa": "por que provavelmente não estava no consenso"
      }}
    ]
  }}
}}
"""

REPORT_PROMPT = """Com base na análise JSON abaixo, escreva um relatório executivo em markdown.

ANÁLISE:
{analise_json}

REGRAS:
- Máximo 400 palavras
- Tom direto, como um analista escrevendo para outro analista
- Use headers markdown (##, ###)
- Destaque red flags em **negrito**
- Termine com "Conclusão" de 2 frases máximo
- NÃO repita todos os dados do JSON — selecione o que é mais relevante
"""


# ── funções principais ───────────────────────────────────────────────────────
def ler_transcricao(caminho: str) -> str:
    """Lê o arquivo de transcrição."""
    path = Path(caminho)
    if not path.exists():
        print(f"❌ Arquivo não encontrado: {caminho}")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def chamar_gemini(prompt: str) -> str:
    """Chama o Gemini e retorna o texto da resposta."""
    resposta = model.generate_content(prompt)
    texto = resposta.text.strip()
    # remove blocos markdown caso o modelo os inclua
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return texto.strip()


def extrair_analise(transcricao: str) -> dict:
    """Chama a API e extrai a análise estruturada em JSON."""
    print("🔍 Extraindo análise da transcrição...")
    prompt = EXTRACTION_PROMPT.format(transcricao=transcricao)
    texto = chamar_gemini(prompt)
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"⚠️  Erro ao parsear JSON: {e}")
        print("Resposta bruta:", texto[:500])
        sys.exit(1)


def gerar_relatorio(analise: dict) -> str:
    """Gera o relatório executivo em markdown."""
    print("📝 Gerando relatório executivo...")
    analise_str = json.dumps(analise, ensure_ascii=False, indent=2)
    prompt = REPORT_PROMPT.format(analise_json=analise_str)
    return chamar_gemini(prompt)


def salvar_saidas(analise: dict, relatorio: str, caminho_saida: str | None):
    """Salva JSON e markdown no disco."""
    json_path = Path("analise_earnings.json")
    json_path.write_text(json.dumps(analise, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ JSON salvo em: {json_path}")

    md_path = Path(caminho_saida) if caminho_saida else Path("relatorio_earnings.md")
    md_path.write_text(relatorio, encoding="utf-8")
    print(f"✅ Relatório salvo em: {md_path}")


def imprimir_resumo(analise: dict):
    """Imprime um resumo rápido no terminal."""
    print("\n" + "═" * 60)
    print(f"  {analise.get('empresa', '—')} | {analise.get('trimestre', '—')}")
    print("═" * 60)
    tom = analise.get("tom_geral", {})
    print(f"  Tom geral:      {tom.get('classificacao', '—')}")
    print(f"  Surprise score: {analise.get('surprise_score', {}).get('score', '—')} / 5")
    flags = analise.get("red_flags", [])
    print(f"  Red flags:      {len(flags)} identificado(s)")
    perguntas = analise.get("perguntas_analisas", [])
    print(f"  Perguntas top:  {len(perguntas)} analisada(s)")
    print("═" * 60 + "\n")


# ── entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Earnings Call Intelligence Tracker")
    parser.add_argument("transcricao", help="Caminho para o arquivo .txt da transcrição")
    parser.add_argument("--output", help="Nome do arquivo markdown de saída (opcional)")
    args = parser.parse_args()

    transcricao = ler_transcricao(args.transcricao)
    print(f"📄 Transcrição carregada: {len(transcricao):,} caracteres\n")

    analise = extrair_analise(transcricao)
    relatorio = gerar_relatorio(analise)

    imprimir_resumo(analise)
    print(relatorio)

    salvar_saidas(analise, relatorio, args.output)


if __name__ == "__main__":
    main()
