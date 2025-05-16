import flet as ft
import os
from pathlib import Path
from PIL import Image
import pyheif
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import io
import logging
import base64

# Configuramos el sistema de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main(page: ft.Page):
    # Configuración de la ventana principal
    page.title = "Watermark App"
    page.padding = 20
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.colors.BLUE_700,
            primary_container=ft.colors.BLUE_100,
            secondary=ft.colors.GREEN_600,
            error=ft.colors.RED_600,
            background=ft.colors.GREY_100,
        )
    )

    # Elementos de la interfaz
    folder_path = ft.TextField(
        label="Carpeta de Imágenes", hint_text="Selecciona la carpeta con imágenes", expand=True, icon=ft.icons.FOLDER, text_size=16
    )
    watermark_path = ft.TextField(
        label="Archivo de Marca de Agua", hint_text="Selecciona la marca de agua (SVG/PNG/JPG/HEIC)", expand=True, icon=ft.icons.IMAGE, text_size=16
    )
    x_coord = ft.TextField(label="Coordenada X", value="10", icon=ft.icons.HORIZONTAL_RULE, text_size=16)
    y_coord = ft.TextField(label="Coordenada Y", value="10", icon=ft.icons.VERTICAL_ALIGN_TOP, text_size=16)
    output_path = ft.TextField(
        label="Carpeta de Salida", hint_text="Selecciona la carpeta de salida", expand=True, icon=ft.icons.SAVE, text_size=16
    )
    base64_input = ft.TextField(
        label="Imagen Base64", hint_text="Pega el string de la imagen en Base64", multiline=True, expand=True, text_size=16
    )
    
    # Contenedor para la vista previa
    preview_container = ft.Container(
        content=ft.Text("Todavía no hay imagen cargada", size=16, color=ft.colors.GREY_600),
        alignment=ft.alignment.center,
        bgcolor=ft.colors.GREY_200,
        border_radius=8,
        expand=True,
        height=page.window.height * 0.4,
    )
    
    status_snackbar = ft.SnackBar(content=ft.Text("Listo para empezar"), bgcolor=ft.colors.BLUE_100)

    # Selectores de archivos
    folder_picker = ft.FilePicker(
        on_result=lambda e: [setattr(folder_path, "value", e.path or ""), page.update()]
    )
    watermark_picker = ft.FilePicker(
        on_result=lambda e: [
            setattr(watermark_path, "value", e.files[0].path if e.files else ""),
            page.update(),
        ]
    )
    output_picker = ft.FilePicker(
        on_result=lambda e: [setattr(output_path, "value", e.path or ""), page.update()]
    )
    page.overlay.extend([folder_picker, watermark_picker, output_picker])

    # Función para mostrar mensajes
    def show_snackbar(message: str, color=ft.colors.BLUE_100):
        status_snackbar.content = ft.Text(message)
        status_snackbar.bgcolor = color
        status_snackbar.open = True
        page.update()

    # Función para diálogos de error
    def show_error_dialog(message: str):
        dialog = ft.AlertDialog(
            title=ft.Text("Error", color=ft.colors.RED_600),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda e: [setattr(page.dialog, "open", False), page.update()])],
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    # Funciones de selección
    def select_folder(e):
        folder_picker.get_directory_path(dialog_title="Selecciona la carpeta de imágenes")

    def select_watermark(e):
        watermark_picker.pick_files(
            dialog_title="Selecciona el archivo de la marca de agua",
            allowed_extensions=["svg", "png", "jpg", "jpeg", "heic"],
            allow_multiple=False,
        )

    def select_output(e):
        output_picker.get_directory_path(dialog_title="Selecciona la carpeta de salida")

    # Cambiar tema
    def toggle_theme(e):
        page.theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        page.update()

    # Cargar imagen
    def load_image(file_path: str) -> Image.Image:
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".heic":
                heif_file = pyheif.read(file_path)
                image = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
            elif ext == ".svg":
                drawing = svg2rlg(file_path)
                img_data = io.BytesIO()
                renderPM.drawToFile(drawing, img_data, fmt="PNG")
                image = Image.open(img_data)
            else:
                image = Image.open(file_path)
            return image.convert("RGBA")
        except Exception as e:
            logger.error(f"No se pudo cargar la imagen {file_path}: {str(e)}")
            show_error_dialog(f"Error al cargar {file_path}: {str(e)}")
            return None

    # Cargar imagen Base64
    def load_base64_image(base64_str: str) -> Image.Image:
        try:
            if base64_str.startswith("data:image"):
                base64_str = base64_str.split(",")[1]
            img_data = base64.b64decode(base64_str)
            image = Image.open(io.BytesIO(img_data))
            return image.convert("RGBA")
        except Exception as e:
            logger.error(f"No se pudo decodificar la imagen Base64: {str(e)}")
            show_error_dialog(f"Imagen Base64 inválida: {str(e)}")
            return None

    # Aplicar marca de agua
    def apply_watermark(image: Image.Image, watermark: Image.Image, x: int, y: int) -> Image.Image:
        if not watermark:
            return image
        img = image.copy()
        watermark = watermark.copy()
        if watermark.width > img.width or watermark.height > img.height:
            watermark.thumbnail((img.width // 2, img.height // 2), Image.LANCZOS)
        x = min(max(0, x), img.width - watermark.width)
        y = min(max(0, y), img.height - watermark.height)
        img.paste(watermark, (x, y), watermark if watermark.mode == "RGBA" else None)
        return img

    # Guardar vista previa
    def save_preview(image: Image.Image) -> str:
        temp_path = os.path.join(os.getcwd(), "temp_preview.png")
        image.convert("RGB").save(temp_path, "PNG")
        return temp_path

    # Procesar imagen
    def process_image(input_path: str, watermark: Image.Image, output_dir: str, x: int, y: int) -> bool:
        image = load_image(input_path)
        if not image:
            return False
        watermarked = apply_watermark(image, watermark, x, y)
        rel_path = os.path.relpath(input_path, folder_path.value)
        output_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            watermarked.convert("RGB").save(output_path, "PNG")
            logger.info(f"Imagen con marca de agua guardada: {output_path}")
            return True
        except Exception as e:
            logger.error(f"No se pudo guardar {output_path}: {str(e)}")
            return False

    # Generar vista previa
    def preview_watermark(e, base64_mode=False):
        if not folder_path.value and not base64_mode:
            show_snackbar("Por favor, selecciona una carpeta válida.", ft.colors.RED_100)
            return
        if not watermark_path.value:
            show_snackbar("Por favor, selecciona una marca de agua.", ft.colors.RED_100)
            return
        try:
            x = int(x_coord.value)
            y = int(y_coord.value)
        except ValueError:
            show_snackbar("Coordenadas inválidas. Usa números.", ft.colors.RED_100)
            return
        watermark = load_image(watermark_path.value)
        if not watermark:
            return
        if base64_mode:
            if not base64_input.value:
                show_snackbar("Por favor, ingresa un string Base64.", ft.colors.RED_100)
                return
            image = load_base64_image(base64_input.value)
            if not image:
                return
            watermarked = apply_watermark(image, watermark, x, y)
            preview_path = save_preview(watermarked)
            preview_container.content = ft.Image(
                src=preview_path,
                fit=ft.ImageFit.CONTAIN,
                border_radius=8,
                expand=True
            )
            show_snackbar("Vista previa de Base64 generada.", ft.colors.GREEN_100)
            page.update()
            return
        supported_extensions = (".png", ".jpg", ".jpeg", ".heic")
        for root, _, files in os.walk(folder_path.value):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    image_path = os.path.join(root, file)
                    image = load_image(image_path)
                    if image:
                        watermarked = apply_watermark(image, watermark, x, y)
                        preview_path = save_preview(watermarked)
                        preview_container.content = ft.Image(
                            src=preview_path,
                            fit=ft.ImageFit.CONTAIN,
                            border_radius=8,
                            expand=True
                        )
                        show_snackbar("Vista previa generada.", ft.colors.GREEN_100)
                        page.update()
                        return
        show_snackbar("No se encontraron imágenes compatibles para la vista previa.", ft.colors.RED_100)

    # Procesar carpeta
    def process_folder(e):
        if not all([folder_path.value, watermark_path.value, output_path.value]):
            show_snackbar("Selecciona carpeta, marca de agua y carpeta de salida.", ft.colors.RED_100)
            return
        if not os.path.exists(folder_path.value) or not os.path.exists(watermark_path.value):
            show_snackbar("Ruta de carpeta o marca de agua inválida.", ft.colors.RED_100)
            return
        try:
            x = int(x_coord.value)
            y = int(y_coord.value)
        except ValueError:
            show_snackbar("Coordenadas inválidas. Usa números.", ft.colors.RED_100)
            return
        watermark = load_image(watermark_path.value)
        if not watermark:
            return
        supported_extensions = (".png", ".jpg", ".jpeg", ".heic")
        processed = 0
        failed = 0
        for root, _, files in os.walk(folder_path.value):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    input_path = os.path.join(root, file)
                    if process_image(input_path, watermark, output_path.value, x, y):
                        processed += 1
                    else:
                        failed += 1
        show_snackbar(
            f"Procesadas {processed} imágenes. Fallidas: {failed}.",
            ft.colors.GREEN_100 if failed == 0 else ft.colors.RED_100,
        )
        logger.info(f"Procesadas {processed} imágenes. Fallidas: {failed}.")

    # Mostrar información
    def show_info_dialog(e):
        dialog = ft.AlertDialog(
            title=ft.Text("Guía de Botones"),
            content=ft.Text(
                "Aquí tienes una explicación de cada botón:\n\n"
                "- 📂 Carpeta de Imágenes: Selecciona la carpeta con las imágenes a procesar.\n"
                "- 🖼️ Marca de Agua: Elige el archivo de la marca de agua (SVG, PNG, JPG, HEIC).\n"
                "- 💾 Carpeta de Salida: Selecciona dónde guardar las imágenes procesadas.\n"
                "- 👁️ Vista Previa: Muestra cómo quedará una imagen con la marca de agua.\n"
                "- ✅ Aplicar Marca de Agua: Procesa todas las imágenes de la carpeta.\n"
                "- 🖼️ Vista Previa Base64: Genera una vista previa de una imagen Base64 con la marca de agua."
            ),
            actions=[ft.TextButton("OK", on_click=lambda e: [setattr(page.dialog, "open", False), page.update()])],
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    # Menú de navegación lateral responsivo
    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        destinations=[
            ft.NavigationRailDestination(icon=ft.icons.HOME, label="Inicio"),
            ft.NavigationRailDestination(icon=ft.icons.LIGHT_MODE, label="Modo Oscuro"),
            ft.NavigationRailDestination(icon=ft.icons.INFO, label="Acerca de"),
        ],
        on_change=lambda e: [
            setattr(page, "dialog", ft.AlertDialog(
                title=ft.Text("Acerca de"),
                content=ft.Text("Watermark App v1.0\nSelecciona 'Modo Oscuro' para cambiar el tema."),
                actions=[ft.TextButton("OK", on_click=lambda e: [setattr(page.dialog, "open", False), page.update()])],
            )),
            setattr(page.dialog, "open", True),
            page.update()
        ] if e.control.selected_index == 2 else toggle_theme(e) if e.control.selected_index == 1 else None,
    )

    # Manejar cambios de tamaño de ventana
    def on_resize(e):
        window_width = page.window.width
        text_size = 16 if window_width >= 600 else 12
        nav_min_width = 80 if window_width >= 600 else 60
        nav_label_type = ft.NavigationRailLabelType.ALL if window_width >= 600 else ft.NavigationRailLabelType.SELECTED
        x_coord_width = 120 if window_width >= 600 else 100
        y_coord_width = 120 if window_width >= 600 else 100
        
        # Ajustar tamaño de fuente de los TextField
        for text_field in [folder_path, watermark_path, x_coord, y_coord, output_path, base64_input]:
            text_field.text_size = text_size
        
        # Ajustar ancho de coordenadas
        x_coord.width = x_coord_width
        y_coord.width = y_coord_width
        
        # Ajustar barra de navegación
        nav_rail.min_width = nav_min_width
        nav_rail.label_type = nav_label_type
        
        # Ajustar altura del contenedor de vista previa
        preview_container.height = page.window.height * 0.4
        
        page.update()

    page.on_resize = on_resize

    # Interfaz responsiva
    page.add(
        ft.Row(
            [
                nav_rail,
                ft.VerticalDivider(width=1),
                ft.Column(
                    [
                        ft.Text("Watermark App", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                content=folder_path,
                                                col={"xs": 8, "sm": 10},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.FOLDER_OPEN,
                                                    on_click=select_folder,
                                                    tooltip="Seleccionar Carpeta de Imágenes",
                                                ),
                                                col={"xs": 4, "sm": 2},
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                content=watermark_path,
                                                col={"xs": 8, "sm": 10},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.IMAGE_SEARCH,
                                                    on_click=select_watermark,
                                                    tooltip="Seleccionar Marca de Agua",
                                                ),
                                                col={"xs": 4, "sm": 2},
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                content=output_path,
                                                col={"xs": 8, "sm": 10},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.SAVE_ALT,
                                                    on_click=select_output,
                                                    tooltip="Seleccionar Carpeta de Salida",
                                                ),
                                                col={"xs": 4, "sm": 2},
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(content=x_coord, col={"xs": 6, "sm": 3}),
                                            ft.Container(content=y_coord, col={"xs": 6, "sm": 3}),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.PREVIEW,
                                                    on_click=preview_watermark,
                                                    tooltip="Generar Vista Previa",
                                                    icon_color=ft.colors.BLUE_700,
                                                ),
                                                col={"xs": 3, "sm": 2},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.CHECK_CIRCLE,
                                                    on_click=process_folder,
                                                    tooltip="Aplicar Marca de Agua",
                                                    icon_color=ft.colors.GREEN_600,
                                                ),
                                                col={"xs": 3, "sm": 2},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.INFO,
                                                    on_click=show_info_dialog,
                                                    tooltip="Guía de Botones",
                                                    icon_color=ft.colors.BLUE_900,
                                                ),
                                                col={"xs": 3, "sm": 2},
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.START,
                                    ),
                                    ft.Divider(),
                                    ft.Text("Vista Previa de Imagen Base64", size=16),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                content=base64_input,
                                                col={"xs": 8, "sm": 10},
                                            ),
                                            ft.Container(
                                                content=ft.IconButton(
                                                    ft.icons.IMAGE,
                                                    on_click=lambda e: preview_watermark(e, base64_mode=True),
                                                    tooltip="Vista Previa de Im	Button: Preview Base64 Image",
                                                ),
                                                col={"xs": 4, "sm": 2},
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Text("Vista Previa:"),
                                                preview_container,
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        padding=10,
                                        bgcolor=ft.colors.GREY_200,
                                        border_radius=8,
                                        expand=True,
                                    ),
                                ],
                                spacing=10,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                            padding=10,
                            expand=True,
                        ),
                    ],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.START,
        )
    )
    page.snack_bar = status_snackbar

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")