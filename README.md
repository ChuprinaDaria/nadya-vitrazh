# Вітражний павільйон

Інтерактивна арт-інсталяція: шматочки вітражів обертаються на штирях. Коли людина підходить — вітражі збираються в єдине зображення. Фото-поза або перегляд телефону — вітражі знову крутяться.

## Встановлення

```bash
pip install -e ".[web]"
```

## Запуск

```bash
# CLI з вебкамери
python -m vitrazh --source 0

# CLI з відеофайлу
python -m vitrazh --source video.mp4

# З дашбордом (http://localhost:8000)
python -m vitrazh --dashboard --source 0
```

## Конфігурація

Скопіюйте та відредагуйте:
```bash
cp config/config_example.yaml config/config.yaml
```

## Тести

```bash
python -m pytest tests/ -v
```

## Архітектура

```
Camera → YOLOv8 (person?) → MediaPipe (pose?) → State Machine → Motors
                                                        ↓
                                                   Dashboard (WS)
```
