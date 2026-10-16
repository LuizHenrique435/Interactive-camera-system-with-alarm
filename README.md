# 🛡️ Sistema Inteligente de Detecção de Movimento

Sistema de monitoramento com **Python**, **OpenCV**, **MediaPipe** e **YOLOv8**.
Além de detectar movimento e disparar um alarme, ele **reconhece rostos, mãos e objetos em tempo real**, mesmo antes de o alarme ser ativado.

---

## ✨ Funcionalidades

| Recurso                         | Descrição                                                                       |
| ------------------------------- | ------------------------------------------------------------------------------- |
| 🙂 **Detecção de rostos**       | Caixa verde em cada rosto detectado (MediaPipe)                                 |
| ✋ **Detecção de mãos**         | Caixa e esqueleto dos dedos nas duas mãos (MediaPipe)                           |
| 📦 **Identificação de objetos** | Reconhece 80 classes (pessoa, celular, garrafa, cadeira...) com YOLOv8          |
| 🕒 **Data e hora**              | Carimbo ao vivo no vídeo, estilo câmera de segurança                            |
| 🚨 **Alarme de movimento**      | Caixas vermelhas na área que se mexeu e alarme sonoro em thread separada        |
| 🧠 **Modo inteligente**         | Só dispara se houver movimento **e** uma pessoa na cena (menos alarmes falsos)  |
| 📸 **Fotos automáticas**        | Salva uma imagem na pasta `capturas/` sempre que o alarme dispara               |
| 🖐️ **Controle por gestos**      | Liga o alarme e tira fotos sem encostar no teclado                              |
| 🔐 **Senha gestual**            | O alarme só desliga com uma sequência secreta de gestos feita no ar             |
| 🤳 **Selfie por gesto**         | Gesto de paz ✌️ inicia contagem 3-2-1, flash na tela e foto limpa com data/hora |
| 📊 **Painel na tela**           | Contador de rostos, mãos e objetos, estado do alarme e do modo inteligente      |

> As detecções de rosto, mão e objeto funcionam **o tempo todo**. O alarme (tecla `A`) só controla a parte de movimento e sirene.

## 🧰 Pré-requisitos

- **Python 3.9 a 3.12**
- Webcam funcional (câmeras externas costumam dar melhor desempenho)
- Windows, Linux ou macOS (no Windows o alarme usa `winsound`; nos outros sistemas, o beep do terminal)
- Internet na **primeira execução**, para baixar o modelo `yolov8n.pt`

## 📦 Instalação

```bash
git clone https://github.com/SEU-USUARIO/NOME-DO-REPOSITORIO.git
cd NOME-DO-REPOSITORIO
pip install -r requirements.txt
```

## ▶️ Como usar

```bash
python motion_detection.py
```

### Controles

| Tecla | Ação                               |
| ----- | ---------------------------------- |
| `A`   | Liga/desliga o alarme de movimento |
| `P`   | Liga/desliga o modo inteligente    |
| `S`   | Salva uma foto manualmente         |
| `F`   | Fecha o programa                   |

### Controle por gestos 🖐️

Mostre a mão para a câmera, **com a palma virada para a lente e os dedos para cima**, e segure o gesto até a barra amarela encher.

| Gesto                      | Quanto tempo | Ação                                 |
| -------------------------- | ------------ | ------------------------------------ |
| 🖐️ Mão aberta              | 2 s          | **Liga** o alarme                    |
| ✌️ Paz (indicador + médio) | 1 s          | Contagem 3-2-1 e **foto**            |
| ✊ → ✌️ → 🖐️ (padrão)      | 0,8 s cada   | **Desliga** o alarme (senha gestual) |

**Por que a senha gestual?** Ligar o alarme com um gesto é inofensivo, mas desligar com um gesto simples permitiria que um intruso o desativasse só acenando. Por isso, com o alarme ligado, apenas a sequência secreta o desliga. Cada gesto precisa ser mantido por 0,8 s, um gesto errado zera a tentativa e o progresso aparece na tela como `Senha gestual: *--`, sem revelar quais são os gestos.

> 🔑 **Troque a senha!** Edite `SECRET_SEQUENCE` no topo do código. Gestos disponíveis: `FIST` (punho), `PEACE` (paz), `OPEN` (mão aberta) e `ONE` (só o indicador).

### Cores na tela

- 🟩 Verde: rosto
- 🟦 Azul-claro: mão
- 🟧 Laranja: objeto identificado
- 🟥 Vermelho: movimento detectado

## ⚙️ Personalização

Todas as configurações ficam no topo do arquivo `motion_detection.py`:

| Parâmetro                  | O que faz                                                        |
| -------------------------- | ---------------------------------------------------------------- |
| `CAMERA_INDEX`             | Escolhe a câmera (0, 1, 2...)                                    |
| `MIN_AREA`                 | Tamanho mínimo do movimento (menor = mais sensível)              |
| `THRESHOLD`                | Sensibilidade a variações de brilho (menor = mais sensível)      |
| `ALARM_TRIGGER`            | Quantos frames de movimento até tocar o alarme                   |
| `YOLO_CONF`                | Confiança mínima para exibir um objeto                           |
| `YOLO_EVERY_N_FRAMES`      | Roda o YOLO a cada N frames (maior = mais rápido, menos preciso) |
| `YOLO_MODEL`               | Troque por `yolov8s.pt` para mais precisão (mais pesado)         |
| `ARM_HOLD`                 | Segundos com a mão aberta para ligar o alarme                    |
| `PHOTO_HOLD` / `COUNTDOWN` | Tempo do gesto de foto e duração da contagem regressiva          |
| `SECRET_SEQUENCE`          | Sua senha gestual (lista de gestos)                              |
| `SEQ_HOLD` / `SEQ_TIMEOUT` | Tempo segurando cada gesto da senha e prazo entre gestos         |

## 🛠️ Problemas comuns

- **Vídeo lento:** aumente `YOLO_EVERY_N_FRAMES` ou use uma câmera externa.
- **Alarme dispara à toa:** aumente `MIN_AREA` e mantenha o modo inteligente ligado.
- **"Não foi possível abrir a câmera":** feche outros programas que usam a webcam ou mude o `CAMERA_INDEX`.
- **Erro com `mediapipe`:** use Python 3.12 ou inferior.
- **Textos sem acento na tela:** limitação do OpenCV ao desenhar texto.

## 🗺️ Roadmap

- [x] Detecção de rostos e mãos
- [x] Identificação de objetos
- [x] Data e hora no vídeo
- [x] Fotos automáticas no alarme
- [x] Gestos de mão para ligar o alarme e tirar foto
- [x] Senha gestual para desligar o alarme
- [ ] Notificação com foto no Telegram
- [ ] Reconhecimento facial (separar conhecidos de desconhecidos)
- [ ] Exigir também o rosto do dono junto com a senha gestual (autenticação em duas etapas)
- [ ] Zonas de detecção desenhadas com o mouse
- [ ] Painel web com Flask

## 🙏 Créditos

Projeto inspirado no sistema de detecção de movimento de **António**
([vídeo no YouTube](https://youtu.be/rBfMr8TV7-A)). A base foi expandida com
visão computacional avançada por **Luiz Henrique**.

## 👤 Autor

**Luiz Henrique**
Feito com 💻, Python e muita curiosidade.
