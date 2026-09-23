import os
import time
import random
import re
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
from playwright.sync_api import sync_playwright, Page, BrowserContext, ElementHandle
from rich.console import Console

from src.form_solver import FormSolver
from src.tracker import ApplicationTracker

console = Console()

class LinkedInEasyApplyBot:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bot_settings = config.get("bot_settings", {})
        self.title_filters = config.get("title_filters", {})
        self.whitelist = [w.lower() for w in self.title_filters.get("whitelist_keywords", [])]
        self.blacklist = [b.lower() for b in self.title_filters.get("blacklist_keywords", [])]
        
        self.profile_dir = os.path.abspath("data/browser_profile")
        os.makedirs(self.profile_dir, exist_ok=True)
        
        self.solver = FormSolver(config)
        self.tracker = ApplicationTracker(self.bot_settings.get("database_path", "data/applications.db"))
        
        self.min_delay = self.bot_settings.get("min_delay_sec", 2.0)
        self.max_delay = self.bot_settings.get("max_delay_sec", 4.5)
        self.max_applications = self.bot_settings.get("max_applications_per_run", 25)
        self.applied_count = 0

    def sleep_random(self, factor: float = 1.0):
        delay = random.uniform(self.min_delay, self.max_delay) * factor
        time.sleep(delay)

    def is_title_relevant(self, title: str) -> Tuple[bool, str]:
        title_lower = title.lower()

        # 1. Comprobar lista negra (Rechazo inmediato de puestos no tech como mesero, chofer, ventas)
        for bad in self.blacklist:
            if bad in title_lower:
                return False, f"Descartado por filtro de lista negra: '{bad}'"

        # 2. Si hay lista blanca definida, debe coincidir al menos una palabra clave
        if self.whitelist:
            for good in self.whitelist:
                if good in title_lower:
                    return True, f"Coincide con palabra clave: '{good}'"
            return False, "No coincide con palabras clave técnicas"

        return True, "Aceptado por defecto"

    def launch_browser(self, playwright, headless: Optional[bool] = None) -> BrowserContext:
        is_headless = self.bot_settings.get("headless", False) if headless is None else headless
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=is_headless,
            channel="chromium",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ],
            viewport={"width": 1280, "height": 850}
        )
        return context

    def interactive_login(self):
        console.print("[bold cyan]Iniciando navegador para iniciar sesión en LinkedIn...[/bold cyan]")
        with sync_playwright() as p:
            context = self.launch_browser(p, headless=False)
            page = context.new_page()
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            
            console.print("[yellow]Por favor, inicia sesión manualmente en la ventana de LinkedIn que se ha abierto.[/yellow]")
            console.print("[yellow]Si te pide código 2FA o verificación, complétala.[/yellow]")
            console.print("[bold green]Una vez que veas tu Feed de LinkedIn, presiona ENTER aquí en la terminal para guardar la sesión...[/bold green]")
            
            input()
            console.print("[bold green]✔ Sesión guardada con éxito en el perfil local.[/bold green]")
            context.close()

    def build_search_url(self, search_query: str, location: str) -> str:
        date_filter = self.bot_settings.get("date_posted_filter", "r604800")
        params = {
            "keywords": search_query,
            "location": location,
            "f_AL": "true", # Easy Apply
            "f_TPR": date_filter,
            "sortBy": "DD"
        }
        query_string = urllib.parse.urlencode(params)
        return f"https://www.linkedin.com/jobs/search/?{query_string}"

    def run_daily_applications(self):
        console.print("[bold blue]🚀 Iniciando ciclo de postulaciones automáticas mejorado...[/bold blue]")
        searches = self.config.get("job_searches", [])
        
        with sync_playwright() as p:
            context = self.launch_browser(p)
            page = context.new_page()
            page.set_default_timeout(45000)
            
            try:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=45000)
                self.sleep_random(1.0)
            except Exception as e:
                console.print(f"[yellow]Aviso navegando al feed: {e}[/yellow]")
            
            if "login" in page.url or "checkpoint" in page.url:
                console.print("[bold red]⚠ No hay sesión iniciada en LinkedIn.[/bold red]")
                console.print("[yellow]Ejecuta primero: python run.py login[/yellow]")
                context.close()
                return

            for search_item in searches:
                if self.applied_count >= self.max_applications:
                    console.print(f"[bold yellow]Límite alcanzado de {self.max_applications} solicitudes para esta sesión.[/bold yellow]")
                    break

                query = search_item.get("query", "")
                location = search_item.get("location", "")
                profile_type = search_item.get("type", "default")
                
                console.print(f"\n[bold cyan]🔍 Buscando:[/bold cyan] '{query}' en '{location}' (Perfil: {profile_type})")
                search_url = self.build_search_url(query, location)
                self.process_search_page(page, search_url, query, profile_type)

            context.close()
            
        console.print(f"\n[bold green]🏁 Finalizado. Total de solicitudes enviadas en este ciclo: {self.applied_count}[/bold green]")
        self.tracker.export_to_csv()

    def process_search_page(self, page: Page, url: str, query: str, profile_type: str):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.sleep_random(1.5)
        except Exception as e:
            console.print(f"[red]Error cargando página de búsqueda: {e}[/red]")
            return

        job_cards = page.query_selector_all(".jobs-search-results-list li.jobs-search-results__list-item, div.job-card-container, div[data-occludable-job-id]")
        console.print(f"Encontradas {len(job_cards)} ofertas en la lista.")

        for card in job_cards:
            if self.applied_count >= self.max_applications:
                break

            try:
                # Extraer Job ID
                job_id = card.get_attribute("data-occludable-job-id") or card.get_attribute("data-job-id")
                if not job_id:
                    link_elem = card.query_selector("a.job-card-list__title, a.job-card-container__link")
                    if link_elem:
                        href = link_elem.get_attribute("href") or ""
                        match = re.search(r"view/(\d+)", href)
                        if match:
                            job_id = match.group(1)

                if not job_id or self.tracker.is_already_applied(job_id):
                    continue

                # Hacer clic en la tarjeta
                card.scroll_into_view_if_needed()
                card.click()
                self.sleep_random(0.8)

                # Obtener Título y Empresa
                title_elem = page.query_selector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1.t-24")
                title = title_elem.inner_text().strip() if title_elem else "Puesto no identificado"

                company_elem = page.query_selector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__primary-description")
                company = company_elem.inner_text().split("·")[0].strip() if company_elem else "Empresa"

                location_elem = page.query_selector(".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet")
                loc_text = location_elem.inner_text().strip() if location_elem else ""

                # Validar relevancia del título (Evitar meseros, cajeros, etc.)
                is_relevant, reason = self.is_title_relevant(title)
                if not is_relevant:
                    console.print(f"[grey50]⏭ Ignorando oferta no relevante ({reason}): '{title}' en {company}[/grey50]")
                    continue

                console.print(f"\n[bold white]🎯 Evaluando oferta tech:[/bold white] [bold cyan]{title}[/bold cyan] en [green]{company}[/green]")

                # Localizar botón Easy Apply
                apply_btn = page.query_selector("button.jobs-apply-button, button.jobs-apply-button--top-card")
                if not apply_btn or not any(text in apply_btn.inner_text() for text in ["Easy Apply", "Solicitud sencilla", "Solicitar"]):
                    console.print(f"[grey62]No tiene Easy Apply directo, omitiendo.[/grey62]")
                    continue

                # Clic en Easy Apply
                apply_btn.click()
                self.sleep_random(1.2)

                # Resolver formulario
                success, note = self.handle_easy_apply_modal(page, profile_type, title)
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

                if success:
                    self.applied_count += 1
                    console.print(f"[bold green]✔ ¡POSTULACIÓN ENVIADA CON ÉXITO! ({self.applied_count}/{self.max_applications})[/bold green]")
                    self.tracker.record_application(job_id, title, company, loc_text, job_url, query, "APPLIED", note)
                else:
                    console.print(f"[yellow]⏩ Omitido ({note}): {title}[/yellow]")
                    self.tracker.record_application(job_id, title, company, loc_text, job_url, query, "SKIPPED", note)

                self.sleep_random(1.5)

            except Exception as e:
                console.print(f"[red]Error procesando tarjeta: {str(e)}[/red]")
                continue

    def handle_easy_apply_modal(self, page: Page, profile_type: str, job_title: str) -> Tuple[bool, str]:
        max_steps = 10
        step = 0
        resume_key = "data" if "data" in job_title.lower() or "sql" in job_title.lower() or "bi" in job_title.lower() else profile_type
        resume_path = os.path.abspath(self.config.get("resumes", {}).get(resume_key, self.config.get("resumes", {}).get("default", "")))

        while step < max_steps:
            step += 1
            self.sleep_random(0.8)

            modal = page.query_selector("div.jobs-easy-apply-modal, div[role='dialog']")
            if not modal:
                return False, "Modal cerrado o no visible"

            # 1. Resolver Inputs de texto, número, tel, email
            text_inputs = modal.query_selector_all("input[type='text'], input[type='number'], input[type='tel'], input[type='email'], textarea")
            for inp in text_inputs:
                try:
                    current_val = inp.input_value()
                    # Extraer el texto de la pregunta/etiqueta asociada
                    label_text = inp.evaluate("""el => {
                        let id = el.id;
                        if (id) {
                            let lbl = document.querySelector(`label[for='${id}']`);
                            if (lbl) return lbl.innerText;
                        }
                        let parent = el.closest('.fb-dash-form-element, .artdeco-text-input--container, .jobs-easy-apply-form-element');
                        if (parent) {
                            let lbl = parent.querySelector('label');
                            if (lbl) return lbl.innerText;
                            return parent.innerText;
                        }
                        return el.getAttribute('aria-label') || '';
                    }""")
                    
                    input_type = inp.get_attribute("type") or "text"
                    resolved_val = self.solver.resolve_text_input(label_text, input_type)

                    # Si el campo está vacío o es un número/salario, llenarlo
                    if resolved_val and (not current_val or current_val == "0" or input_type == "number"):
                        inp.fill("")
                        inp.fill(resolved_val)
                        console.print(f"  [cyan]Campo llenado:[/cyan] '{label_text.strip()[:40]}...' -> [bold green]{resolved_val}[/bold green]")
                        self.sleep_random(0.2)
                except Exception:
                    pass

            # 2. Resolver Selects / Dropdowns estándar
            selects = modal.query_selector_all("select")
            for sel in selects:
                try:
                    label_text = sel.evaluate("""el => {
                        let id = el.id;
                        if (id) {
                            let lbl = document.querySelector(`label[for='${id}']`);
                            if (lbl) return lbl.innerText;
                        }
                        let parent = el.closest('.fb-dash-form-element, .jobs-easy-apply-form-element');
                        if (parent) {
                            let lbl = parent.querySelector('label');
                            if (lbl) return lbl.innerText;
                            return parent.innerText;
                        }
                        return '';
                    }""")
                    options = [opt.inner_text().strip() for opt in sel.query_selector_all("option")]
                    chosen_opt = self.solver.resolve_dropdown(label_text, options)
                    if chosen_opt:
                        sel.select_option(label=chosen_opt)
                        console.print(f"  [cyan]Dropdown seleccionado:[/cyan] '{label_text.strip()[:40]}...' -> [bold green]{chosen_opt}[/bold green]")
                        self.sleep_random(0.2)
                except Exception:
                    pass

            # 3. Resolver Grupos de Radio Buttons (Fieldsets)
            fieldsets = modal.query_selector_all("fieldset")
            for fs in fieldsets:
                try:
                    legend_text = fs.evaluate("""el => {
                        let legend = el.querySelector('legend');
                        return legend ? legend.innerText : el.innerText;
                    }""")
                    radio_labels = fs.query_selector_all("label")
                    option_texts = [lbl.inner_text().strip() for lbl in radio_labels]
                    chosen_text = self.solver.resolve_boolean_question(legend_text, option_texts)
                    
                    for lbl in radio_labels:
                        if chosen_text and chosen_text.lower() in lbl.inner_text().lower():
                            radio_input = lbl.query_selector("input[type='radio']")
                            if radio_input and not radio_input.is_checked():
                                lbl.click()
                                console.print(f"  [cyan]Radio marcado:[/cyan] '{legend_text.strip()[:40]}...' -> [bold green]{chosen_text}[/bold green]")
                                self.sleep_random(0.2)
                            break
                except Exception:
                    pass

            # 4. Resolver Checkboxes (Términos, privacidad, etc.)
            checkboxes = modal.query_selector_all("input[type='checkbox']")
            for cb in checkboxes:
                try:
                    if not cb.is_checked():
                        # Generalmente son acuerdos de consentimiento o privacidad
                        cb.check(force=True)
                        self.sleep_random(0.2)
                except Exception:
                    pass

            # 5. Adjuntar CV si solicita archivo
            file_input = modal.query_selector("input[type='file']")
            if file_input and os.path.exists(resume_path):
                try:
                    file_input.set_input_files(resume_path)
                    console.print(f"  [magenta]📄 CV adjuntado:[/magenta] {os.path.basename(resume_path)}")
                    self.sleep_random(0.8)
                except Exception:
                    pass

            # 6. Comprobar botón de Enviar / Submit final
            submit_btn = modal.query_selector("button[aria-label='Submit application'], button[aria-label='Enviar solicitud'], button:has-text('Submit application'), button:has-text('Enviar solicitud')")
            if submit_btn and submit_btn.is_visible():
                submit_btn.click()
                console.print("  [bold green]Enviando solicitud final...[/bold green]")
                self.sleep_random(2.0)
                
                # Cerrar modal de confirmación
                close_btn = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Descartar'], button.artdeco-modal__dismiss")
                if close_btn:
                    close_btn.click()
                return True, "Enviado exitosamente"

            # 7. Comprobar botón Revisar / Review
            review_btn = modal.query_selector("button[aria-label='Review your application'], button[aria-label='Revisar solicitud'], button:has-text('Review'), button:has-text('Revisar')")
            if review_btn and review_btn.is_visible():
                review_btn.click()
                self.sleep_random(0.8)
                continue

            # 8. Comprobar botón Siguiente / Next
            next_btn = modal.query_selector("button[aria-label='Continue to next step'], button[aria-label='Continuar al siguiente paso'], button:has-text('Next'), button:has-text('Siguiente')")
            if next_btn and next_btn.is_visible():
                next_btn.click()
                self.sleep_random(0.8)
                
                # Verificar si quedaron campos requeridos con error
                error = modal.query_selector(".artdeco-inline-feedback--error, div[data-test-form-element-error-messages]")
                if error:
                    err_msg = error.inner_text().strip()
                    console.print(f"  [yellow]⚠ Campo requerido bloqueante: {err_msg}[/yellow]")
                    self.dismiss_modal(page)
                    return False, f"Pregunta compleja/bloqueante: {err_msg}"
                continue

            # Si no hay botones de acción visibles
            break

        self.dismiss_modal(page)
        return False, "Formulario complejo o sin botón de avance"

    def dismiss_modal(self, page: Page):
        try:
            dismiss_btn = page.query_selector("button[aria-label='Dismiss'], button[aria-label='Descartar'], button.artdeco-modal__dismiss")
            if dismiss_btn:
                dismiss_btn.click()
                self.sleep_random(0.5)
                discard_btn = page.query_selector("button[data-control-name='discard_application_confirm_btn'], button:has-text('Discard'), button:has-text('Descartar')")
                if discard_btn:
                    discard_btn.click()
        except Exception:
            pass
