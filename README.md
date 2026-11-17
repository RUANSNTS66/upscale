# Upscale com IA

Aplicativo desktop em Python para **aumentar a resolução de imagens com inteligência artificial**, usando o modelo [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN). Basta arrastar a imagem para a janela, escolher **2x** ou **4x** e pronto.

<!-- Dica: coloque aqui um print da janela, por exemplo: ![Screenshot](docs/screenshot.png) -->

## Funcionalidades

- **Arrastar e soltar** imagens (ou clicar para escolher) com resposta visual ao arrastar
- **Prévia** da imagem logo que ela é adicionada
- Escolha de ampliação de **2x ou 4x**
- Processamento de **várias imagens** de uma vez, ou de uma **pasta inteira**
- **Janela de log** mostrando o que está acontecendo (carregamento do modelo, progresso, tempo, erros)
- Usa a **GPU NVIDIA (CUDA)** automaticamente, se disponível; caso contrário, roda na CPU
- Baixa o modelo sozinho na primeira execução (~64 MB)
- Botão para **adicionar nova imagem** e para **abrir a pasta do resultado**

## Requisitos

- Windows
- **Python 3.11 ou 3.12** (o Python 3.14 ainda não funciona, pois o `basicsr` não instala nele)
- Opcional: placa de vídeo NVIDIA para processar bem mais rápido

## Instalação

```bash
# 1. Baixe o projeto
git clone https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
cd SEU-REPOSITORIO

# 2. Crie e ative um ambiente virtual com Python 3.12
py -3.12 -m venv venv
venv\Scripts\activate

# 3. Instale as dependências
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Com placa NVIDIA, instale o PyTorch com CUDA antes do passo 3, usando o comando gerado em [pytorch.org](https://pytorch.org/get-started/locally/).

## Como usar

```bash
python upscale_gui.py
```

1. Escolha **2x** ou **4x**.
2. Arraste uma ou mais imagens (ou uma pasta) para a área azul, ou clique nela para escolher os arquivos.
3. Acompanhe o progresso pela barra e pela janela de log.
4. O resultado é salvo **ao lado da imagem original**, com o sufixo `_x2` ou `_x4` (exemplo: `foto.jpg` → `foto_x4.png`).

Formatos aceitos: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`. A saída é sempre `.png`, para não perder qualidade.

## 🛠️ Solução de problemas

| Problema | Solução |
|---|---|
| Erro ao instalar o `basicsr` (`KeyError: '__version__'`) | Você está no Python 3.14. Use o Python 3.11 ou 3.12 em um ambiente virtual. |
| O `basicsr` continua falhando | Instale a versão mantida pela comunidade: `pip install basicsr-fixed realesrgan` |
| Erro de `functional_tensor` | O programa já aplica essa correção automaticamente. Se persistir, atualize os pacotes. |
| `out of memory` | Diminua o valor de `tile=256` no arquivo `upscale_gui.py` (por exemplo, para `128`). |
| Muito lento | Sem GPU NVIDIA o processamento roda na CPU. Teste primeiro com uma imagem pequena. |

## Tecnologias

- [Python](https://www.python.org/)
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) e [BasicSR](https://github.com/XPixelGroup/BasicSR)
- [PyTorch](https://pytorch.org/)
- [OpenCV](https://opencv.org/) e [Pillow](https://python-pillow.org/)
- [Tkinter](https://docs.python.org/3/library/tkinter.html) e [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) para a interface

## Créditos

O upscale é feito pelo modelo **Real-ESRGAN** (`RealESRGAN_x4plus`), criado por Xintao Wang e colaboradores. Este projeto é apenas uma interface em volta dele.

