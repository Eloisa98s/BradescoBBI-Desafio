"""
Case 2 — Macro Scenario Engine
Bradesco BBI — Estágio Tech/AI em Equity Strategy

Como usar:
    python engine.py
    python engine.py --cenario "Selic cai para 10%, dólar em R$5,20..."
    python engine.py --output meu_relatorio.md
"""

import json
import sys
import argparse
import os
from pathlib import Path
import google.generativeai as genai

# ── carrega o arquivo .env se existir ───────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ── cliente da API ──────────────────────────────────────────────────────────
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="""Você é um estrategista sênior de Equity Strategy focado no mercado brasileiro.

Você traduz cenários macroeconômicos em impactos setoriais e recomendações de ações para a Bolsa brasileira (B3/Ibovespa).

Suas análises:
- São baseadas em mecanismos econômicos reais e verificáveis
- Citam tickers reais do Ibovespa com justificativas baseadas nas características das empresas
- São honestas sobre incertezas e riscos
- NUNCA inventam dados ou resultados financeiros específicos
- Explicam claramente o mecanismo de transmissão: POR QUE o cenário impacta esse setor/empresa

Setores relevantes da B3: Bancos, Varejo, Commodities (Petróleo, Mineração), Utilidades Elétricas,
Telecomunicações, Saúde, Construção Civil, Agronegócio, Tecnologia, Transportes/Logística."""
)


# ── prompts ─────────────────────────────────────────────────────────────────
ANALYSIS_PROMPT = """Analise o cenário macroeconômico abaixo e retorne um JSON estruturado.

CENÁRIO MACRO:
{cenario}

Retorne APENAS o JSON abaixo, sem texto antes ou depois, sem markdown:

{{
  "cenario_resumido": "resumo do cenário em 1-2 frases",
  "setores_beneficiados": [
    {{
      "setor": "nome do setor",
      "impacto": "Forte | Moderado",
      "mecanismo": "1-2 frases explicando COMO e POR QUE esse setor é beneficiado"
    }}
  ],
  "setores_prejudicados": [
    {{
      "setor": "nome do setor",
      "impacto": "Forte | Moderado",
      "mecanismo": "1-2 frases explicando COMO e POR QUE esse setor é prejudicado"
    }}
  ],
  "tickers_positivos": [
    {{
      "ticker": "XXXX3",
      "empresa": "Nome da Empresa",
      "setor": "setor",
      "justificativa": "por que ESSA empresa especificamente"
    }}
  ],
  "tickers_negativos": [
    {{
      "ticker": "XXXX3",
      "empresa": "Nome da Empresa",
      "setor": "setor",
      "justificativa": "por que ESSA empresa especificamente"
    }}
  ],
  "riscos_da_tese": [
    {{
      "risco": "descrição do risco",
      "impacto_se_ocorrer": "o que mudaria na análise"
    }}
  ],
  "confidence": {{
    "nivel": "Alto | Médio | Baixo",
    "razao": "por que esse nível de confiança"
  }}
}}

REGRAS:
- Exatamente 5 setores beneficiados e 5 prejudicados
- Exatamente 3 tickers positivos e 3 negativos — todos reais do Ibovespa
- Exatamente 3 riscos
- Mecanismos de transmissão específicos, não genéricos
"""

REPORT_PROMPT = """Com base na análise JSON abaixo, escreva um relatório executivo em markdown.

ANÁLISE:
{analise_json}

REGRAS:
- Máximo 500 palavras
- Tom direto — analista escrevendo para gestor de portfólio
- Use headers markdown (##, ###)
- Apresente setores em tabela markdown
- Destaque riscos em **negrito**
- Termine com uma seção "Nossa View" de 2-3 frases
- NÃO repita tudo do JSON — síntese é mais valiosa que lista completa
"""


# ── funções ──────────────────────────────────────────────────────────────────
def coletar_cenario(cenario_arg: str | None) -> str:
    """Pega o cenário do argumento CLI ou pede ao usuário."""
    if cenario_arg:
        return cenario_arg

    print("=" * 60)
    print("  MACRO SCENARIO ENGINE — Bradesco BBI")
    print("=" * 60)
    print("\nDescreva o cenário macroeconômico em linguagem natural.")
    print("Exemplos de variáveis a incluir:")
    print("  - Selic, IPCA, câmbio (BRL/USD)")
    print("  - Crescimento do PIB, desemprego")
    print("  - Ambiente externo (Fed, China, commodities)")
    print("  - Política fiscal brasileira")
    print("\nCenário (pressione Enter duas vezes quando terminar):\n")

    linhas = []
    while True:
        linha = input()
        if linha == "" and linhas and linhas[-1] == "":
            break
        linhas.append(linha)

    cenario = "\n".join(linhas).strip()
    if not cenario:
        print("❌ Cenário vazio. Tente novamente.")
        sys.exit(1)
    return cenario


def chamar_gemini(prompt: str) -> str:
    """Chama o Gemini e retorna o texto da resposta."""
    resposta = model.generate_content(prompt)
    texto = resposta.text.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return texto.strip()


def analisar_cenario(cenario: str) -> dict:
    """Chama a API e retorna análise estruturada."""
    print("\n🔍 Analisando cenário macroeconômico...")
    prompt = ANALYSIS_PROMPT.format(cenario=cenario)
    texto = chamar_gemini(prompt)
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"⚠️  Erro ao parsear JSON: {e}")
        print("Resposta bruta:", texto[:500])
        sys.exit(1)


def gerar_relatorio(analise: dict) -> str:
    """Gera relatório markdown executivo."""
    print("📝 Gerando relatório executivo...")
    analise_str = json.dumps(analise, ensure_ascii=False, indent=2)
    prompt = REPORT_PROMPT.format(analise_json=analise_str)
    return chamar_gemini(prompt)


def salvar_saidas(analise: dict, relatorio: str, caminho_saida: str | None):
    """Salva JSON e markdown."""
    json_path = Path("analise_macro.json")
    json_path.write_text(json.dumps(analise, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ JSON salvo em: {json_path}")

    md_path = Path(caminho_saida) if caminho_saida else Path("relatorio_macro.md")
    md_path.write_text(relatorio, encoding="utf-8")
    print(f"✅ Relatório salvo em: {md_path}")


def imprimir_resumo(analise: dict):
    """Imprime resumo no terminal."""
    print("\n" + "═" * 60)
    print(f"  CENÁRIO: {analise.get('cenario_resumido', '—')}")
    print("═" * 60)

    print("\n  📈 SETORES BENEFICIADOS:")
    for s in analise.get("setores_beneficiados", [])[:5]:
        print(f"    + {s['setor']} [{s['impacto']}]")

    print("\n  📉 SETORES PREJUDICADOS:")
    for s in analise.get("setores_prejudicados", [])[:5]:
        print(f"    - {s['setor']} [{s['impacto']}]")

    print("\n  🟢 TICKERS POSITIVOS:")
    for t in analise.get("tickers_positivos", []):
        print(f"    {t['ticker']} — {t['empresa']}")

    print("\n  🔴 TICKERS NEGATIVOS:")
    for t in analise.get("tickers_negativos", []):
        print(f"    {t['ticker']} — {t['empresa']}")

    conf = analise.get("confidence", {})
    print(f"\n  Confiança da análise: {conf.get('nivel', '—')}")
    print("═" * 60 + "\n")


# ── entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Macro Scenario Engine")
    parser.add_argument("--cenario", help="Cenário macro em texto (opcional)")
    parser.add_argument("--output", help="Nome do arquivo markdown de saída (opcional)")
    args = parser.parse_args()

    cenario = coletar_cenario(args.cenario)
    analise = analisar_cenario(cenario)
    relatorio = gerar_relatorio(analise)

    imprimir_resumo(analise)
    print(relatorio)

    salvar_saidas(analise, relatorio, args.output)


if __name__ == "__main__":
    main()
