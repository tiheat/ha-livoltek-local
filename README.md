# Livoltek Local para Home Assistant

Integração customizada que lê um **inversor Livoltek grid-tie** direto na rede local, por **Modbus TCP**,
através do módulo Wi-Fi que já vem no inversor (Hi-Flying **HF-LPB130**, servidor TCP na porta 502).
Sem nuvem e sem hardware extra.

- **Uma requisição por leitura:** os registradores 4100–4157 são lidos de uma vez, a cada 60 s por padrão.
- **Conexão curta:** cada leitura abre a conexão, lê e fecha. Manter a conexão aberta ou ler registrador por
  registrador atrapalha o envio de dados que o próprio módulo faz para a nuvem da Livoltek.
- **À noite** o inversor desliga e os sensores ficam indisponíveis até ele voltar.

## Sensores

| Sensor | Unidade | Registrador | Escala |
|---|---|---|---|
| Potência CA | W | 4100 | × 0,1 |
| Energia hoje | kWh | 4136 | × 0,001 |
| Frequência | Hz | 4101 | × 0,01 |
| String 1 tensão / corrente / potência | V / A / W | 4112 / 4113 / 4115 | × 0,1 / × 0,01 / × 0,1 |
| String 2 tensão / corrente / potência | V / A / W | 4116 / 4117 / 4119 | × 0,1 / × 0,01 / × 0,1 |
| Temperatura | °C | 4124 | × 1 |
| Estado | — | 4125 | código (3 = gerando) |
| Fator de potência | — | 4157 | × 0,001 |

No painel de Energia, use **Energia hoje** como fonte solar e **Potência CA** como potência.

O mapa de registradores foi identificado com dados ao vivo e conferido pela eficiência
(potência CA ≈ 96–98% da soma das strings) e pela taxa de subida da energia do dia.
A potência é um registrador de 16 bits com escala 0,1 W, então vai até 6553 W.

## Instalação

Requer Home Assistant 2025.8 ou superior. O ícone da integração (pasta `brand/`) aparece a partir do 2026.3;
os SVGs de origem ficam em `assets/` (`mise run icons` gera os PNGs).

**Via Marketplace (Home Assistant 2026.11+) ou HACS (recomendado):**

1. Em *Configurações → Marketplace* (ou HACS, em versões anteriores), abra *Repositórios customizados* e adicione
   `https://github.com/tiheat/ha-livoltek-local` com a categoria *Integração*.
2. Instale **Livoltek Local** e reinicie o Home Assistant.
3. Em *Configurações → Dispositivos e serviços → Adicionar integração*, procure **Livoltek Local** e informe
   o IP do módulo Wi-Fi (porta 502, ID Modbus 1).

Novas versões aparecem como atualização no próprio Home Assistant, a partir das releases deste repositório.

**Via SSH (desenvolvimento):** com o host `ha` configurado no `~/.ssh/config`, copie o código local e reinicie:

```bash
mise run deploy
```

```bash
mise run restart
```

O intervalo de leitura pode ser ajustado em *Configurar* na integração.

## Desenvolvimento

```bash
mise run lint
```

```bash
mise run test
```

## Versionamento

Cada push ou merge na `main` que passa na CI gera uma versão automaticamente com
[semantic-release](https://semantic-release.gitbook.io/), a partir dos
[commits convencionais](https://www.conventionalcommits.org/) desde a última tag:

| Commit | Versão |
|---|---|
| `fix: ...`, `perf: ...`, `refactor: ...`, `build: ...` | patch (1.0.**1**) |
| `feat: ...` | minor (1.**1**.0) |
| `BREAKING CHANGE:` no rodapé, ou `feat!:` | major (**2**.0.0) |
| `docs:`, `chore:`, `test:`, `ci:`, `style:` | sem nova versão |

O job `release` atualiza a versão no `manifest.json` e no `pyproject.toml`, cria o commit
`chore: release X.Y.Z`, a tag `vX.Y.Z` e a release no GitHub com as notas geradas dos commits e o
`livoltek_local.zip` anexado (usado pelo Marketplace/HACS para instalar e atualizar).
