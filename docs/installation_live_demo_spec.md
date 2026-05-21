# Vitrazh Live Demo — Spec + Known Issues

## Мета

Split-screen на ноутбуці (Windows, Python 3.13, MediaPipe):
- **Ліва панель**: об'ємна 3D фігура людини в реальному часі з камери
- **Права панель**: 3D кімната-галерея з Blender з крутящимися вітражами

## Поточний стан

Скрипт `scripts/vitrazh_live.py` запускається на ноуті через SSH:
- MediaPipe Pose Landmarker працює, детектить людину
- FastAPI + WebSocket сервер на порту 8000
- Браузер відкриває `installation.html`
- Стан коректний: `teasing` при 1 людині, стейт-машина працює

## ПРОБЛЕМА 1: Скелет — палички без тіла

### Що просили
- Об'ємне схематичне зображення людини
- Голова як контур (овал)
- Тулуб з об'ємом
- Більше точок на тілі

### Що пробували і НЕ допомогло

**Спроба 1: Canvas 2D enhanced** (в `installation.html`)
- Додали: овал голови по ear-to-ear відстані, заливка тулуба (shoulders→hips quad),
  трикутники рук/ніг, інтерпольовані точки вздовж кісток
- Результат: **все одно точки + палички**. Canvas 2D принципово не дає об'єму.
  Навіть з заливками виглядає плоско. Голова відокремлена від тіла.
- Код: edit в `drawRealDetections()` — torso fill, head oval, interpolated dots

**Причина невдачі:**
Canvas 2D малює плоскі фігури. Landmarks — це набір точок без зв'язків.
Щоб зробити "тіло", потрібні або:
- 3D геометрія (capsules/cylinders між landmark-ами) з освітленням
- Готова 3D mesh (VRM/SMPL) яку анімують по landmarks

### Рекомендований підхід: Three.js Capsule Body

Замінити Canvas на другий Three.js renderer. Будувати тіло з:
- 13× `CapsuleGeometry` (кінцівки, тулуб, шия)
- 1× `SphereGeometry` (голова)
- `MeshStandardMaterial` з green glow

Деталі див. нижче в "Implementation Plan".

### Альтернативи (досліджено через Context7)

| Підхід | Оцінка |
|--------|--------|
| **Three.js Capsule Body** | Рекомендовано. 0 нових deps, ~200 LOC, вже є Three.js |
| **VRM + Kalidokit** | Найреалістичніше, але Kalidokit залежить від deprecated Holistic API, потрібен VRM файл 2-5MB |
| **SMPL/SMPL-X (C++)** | Gold standard для body mesh, але академічна ліцензія, складний setup |
| **OpenPose (C++/CUDA)** | Real-time body rendering, потребує GPU |
| **Canvas 2D enhanced** | Не працює. Спробовано. Виглядає плоско. |

## ПРОБЛЕМА 2: Кімната з Blender не відображається

### Що просили
- 3D кімната-галерея з Blender за вітражами
- Стіни, стеля, підлога, освітлення

### Що пробували і НЕ допомогло

**Спроба 1: Перевірка через MCP Blender**
- `mcp__blender__get_scene_info` → знайдено 93 об'єкти
- `mcp__blender__execute_blender_code` → перелік всіх об'єктів
- `Gallery_Room` ІСНУЄ: mesh з 8 вершин, 5 полігонів (box без однієї грані)
- Матеріал `mat_gallery_room`: Principled BSDF, Base Color (0.85, 0.85, 0.85), Roughness 0.7
- Bounding box: (-6, -5, -4.56) → (6, 5, 5.44) в Blender coords

**Спроба 2: Діагноз — передня стіна блокує вид**
- `Gallery_Room` має 5 граней (box з відкритою задньою стіною)
- Face normals: (1,0,0), **(0,-1,0)**, (-1,0,0), (0,0,1), (0,0,-1)
- Грань з normal (0,-1,0) = передня стіна (найближча до камери)
- В Three.js після конвертації coords: ця стіна на z≈5, камера на z=9
- Камера дивиться на ЗОВНІШНЮ сторону передньої стіни → вона блокує ВСЕ за нею

**Спроба 3: Видалення передньої стіни + перезекспорт GLB**
- `mcp__blender__execute_blender_code` → bmesh → видалив грань з normal.y < -0.9
- Перезекспортував GLB (7.9 MB)
- Результат: **"чорний квадрат за вітражем"** замість кімнати

**Спроба 4: Процедурна кімната (Three.js fallback)**
- Додали в `installation.html` програмну кімнату з `PlaneGeometry` (5 стін)
- Матеріал: dark gray (0x1a1714), DoubleSide
- Логіка: ховати якщо GLB має свою кімнату (`meshStats.room > 0`)
- Результат: не видно або зливається з фоном

### Невирішені питання по кімнаті

1. **Координатна система**: Blender Z-up → Three.js Y-up.
   Конвертація: Blender (x,y,z) → Three.js (x, z, -y).
   Камера в Blender: (0, -5.5, -0.5) → Three.js: (0, -0.5, 5.5).
   Камера в HTML: (0, 0.3, 9) — значно далі ніж в Blender!

2. **Матеріал Gallery_Room** — Base Color 0.85 (світло-сірий) але Three.js може
   рендерити його інакше через різницю в тонемапінгу (ACESFilmicToneMapping).

3. **Освітлення** — Blender сцена має 5 spot lights + ceiling + back light.
   GLB експортований БЕЗ lights (`export_lights=False`). Three.js сцена має тільки
   ambient (0.5) + 2 point lights — можливо недостатньо для видимості стін.

4. **Camera position** — Може потрібно або:
   - Перемістити камеру всередину кімнати (z≈4 замість z=9)
   - Або відкрити кімнату і з переду, щоб камера бачила інтер'єр

5. **Material override** — Код в `installation.html` робить:
   ```javascript
   child.material.transparent = false;
   child.material.opacity = 1.0;
   child.material.side = THREE.DoubleSide;
   ```
   Це може конфліктувати з GLB матеріалами кімнати.

### Blender сцена — повний список об'єктів

```
LIGHTS (6):
  Back_Light        (0.0, 0.4, 0.0)
  Ceiling_Light     (0.0, 0.0, 4.94)
  Spot_1           (-2.5, -3.0, 5.0)
  Spot_2            (2.5, -3.0, 5.0)
  Spot_3            (0.0, -2.5, 5.0)
  Spot_4           (-5.5, -2.0, 4.0)
  Spot_5            (5.5, -2.0, 4.0)

CAMERA (1):
  Camera_Front      (0.0, -5.5, -0.5)

ROOM (1):
  Gallery_Room      (0.0, 0.0, 0.0)  — 8 verts, 4 faces (після видалення передньої)
                    BB: (-6,-5,-4.56) → (6,5,5.44)
                    Material: mat_gallery_room (gray 0.85, rough 0.7)

RODS (7):
  rod_0..rod_6      x: -1.44 → 1.44, step 0.48

VITRAZH PANELS (63):
  vitrazh_01..vitrazh_63
  Grid 7×9, spacing 0.48
  z: -1.92 → 1.92 (Blender), y: 0 (flat plane)

DECO (17):
  deco_top_*, deco_bottom_*  — decorative panels above/below main grid
```

## Implementation Plan — Capsule Body

### Що потрібно змінити

1. **Ліва панель** (`#leftPanel`): замінити `<canvas>` на другий Three.js renderer
2. **Створити body mesh**: 13 capsules + 1 sphere + joint spheres
3. **WebSocket → body update**: маппінг landmarks на позиції capsules
4. **Smoothing**: EMA на позиціях landmarks (α=0.3)

### Body Segments

```
HEAD:        SphereGeometry(r=0.09)   above midpoint(#11, #12)
NECK:        Capsule  midpoint(#11,#12) → head_base      r=0.04
TORSO:       Capsule  midpoint(#11,#12) → midpoint(#23,#24)  r=0.12→0.10
L_UPPER_ARM: Capsule  #11 → #13                          r=0.035
R_UPPER_ARM: Capsule  #12 → #14                          r=0.035
L_FOREARM:   Capsule  #13 → #15                          r=0.03
R_FOREARM:   Capsule  #14 → #16                          r=0.03
L_THIGH:     Capsule  #23 → #25                          r=0.05
R_THIGH:     Capsule  #24 → #26                          r=0.05
L_SHIN:      Capsule  #25 → #27                          r=0.035
R_SHIN:      Capsule  #26 → #28                          r=0.035
L_FOOT:      Capsule  #27 → #31                          r=0.03
R_FOOT:      Capsule  #28 → #32                          r=0.03
```

(# = MediaPipe landmark index)

### Positioning Algorithm

```javascript
function updateCapsule(mesh, lmA, lmB, scaleW, scaleH) {
    if (lmA[2] < 0.4 || lmB[2] < 0.4) { mesh.visible = false; return; }
    mesh.visible = true;

    const a = new THREE.Vector3(lmA[0] * scaleW, -lmA[1] * scaleH, (lmA[2] || 0) * 0.5);
    const b = new THREE.Vector3(lmB[0] * scaleW, -lmB[1] * scaleH, (lmB[2] || 0) * 0.5);
    const mid = a.clone().add(b).multiplyScalar(0.5);
    const dir = b.clone().sub(a);
    const len = dir.length();

    mesh.position.lerp(mid, 0.3);           // smoothing
    mesh.scale.y = len / mesh.userData.baseH; // stretch to fit
    const up = new THREE.Vector3(0, 1, 0);
    const quat = new THREE.Quaternion().setFromUnitVectors(up, dir.normalize());
    mesh.quaternion.slerp(quat, 0.3);        // smooth rotation
}
```

### Material

```javascript
const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x22c55e,
    emissive: 0x0a3d1a,
    emissiveIntensity: 0.5,
    roughness: 0.7,
    metalness: 0.1,
    transparent: true,
    opacity: 0.85,
});
```

## Implementation Plan — Gallery Room Fix

### Підхід A: Камеру всередину + експорт з lights

1. В `installation.html` змінити камеру: `cam.position.set(0, 0.3, 4)` (всередину кімнати)
2. Перезекспортувати GLB з `export_lights=True`
3. В Three.js: НЕ override матеріали кімнати (тільки для vitrazh панелей)

### Підхід B: Видалити передню і задню стіну, камера ззовні

1. В Blender видалити 2 грані (front + back) через MCP
2. Камера залишається на z=9
3. Додати більше освітлення в Three.js для видимості стін

### Підхід C: Окремий GLB для кімнати

1. Експортувати Gallery_Room окремо в `gallery_room.glb`
2. Завантажувати в Three.js окремим loader
3. Контролювати матеріали і видимість незалежно

## Файли

| Файл | Призначення |
|------|------------|
| `scripts/vitrazh_live.py` | Standalone сервер для ноута (MediaPipe + FastAPI) |
| `vitrazh/dashboard/static/installation.html` | Split-screen UI (skeleton + 3D scene) |
| `vitrazh/dashboard/static/vitrazh_scene.glb` | 3D сцена з Blender (7.9 MB) |
| `vitrazh_scene.blend` | Blender source (93 об'єкти, 86 матеріалів) |

## MCP Blender Tools для діагностики

```
mcp__blender__get_scene_info        — список всіх об'єктів
mcp__blender__get_object_info       — деталі конкретного об'єкта (BB, materials)
mcp__blender__execute_blender_code  — довільний Python код в Blender
mcp__blender__get_viewport_screenshot — скріншот viewport
```

## Середовище тестування

- Десктоп: Ubuntu, CPU без AVX (MediaPipe крашиться)
- Ноут: Windows, ja@192.168.1.12, Python 3.13, SSH password auth
- MCP сервер `laptop-ssh` для SSH команд
- SSH: `sshpass -p '1234' ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no ja@192.168.1.12`
- Файли на ноуті: `C:\Users\ja\vitrazh_live\` (script + static/)
