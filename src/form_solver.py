import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("FormSolver")

class FormSolver:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.personal_info = config.get("personal_info", {})
        self.form_answers = config.get("form_answers", {})
        self.experience_years = self.form_answers.get("experience_years", {})
        self.boolean_questions = self.form_answers.get("boolean_questions", {})
        self.text_mappings = self.form_answers.get("text_mappings", {})

    def resolve_text_input(self, label_text: str, input_type: str = "text") -> Optional[str]:
        label_lower = label_text.lower().strip()

        # 1. PREGUNTAS NUMÉRICAS DE EXPERIENCIA (Prioridad máxima sobre palabras individuales)
        if any(k in label_lower for k in ["cuántos años", "cuantos años", "how many years", "años de experiencia", "years of experience", "experiencia tienes", "tiempo de experiencia"]):
            for tech, years in self.experience_years.items():
                if tech != "default" and re.search(r'\b' + re.escape(tech) + r'\b', label_lower):
                    return str(years)
            return str(self.experience_years.get("default", 1))

        # 2. Salario / Remuneración / Expectativa Salarial
        if any(k in label_lower for k in ["salary", "salario", "sueldo", "remuneración", "remuneracion", "compensation", "expectativa salarial", "pretensión", "pretension"]):
            return str(self.text_mappings.get("salary_expectation", "1200"))

        # 3. Teléfono / Celular / Móvil
        if any(k in label_lower for k in ["phone", "teléfono", "telefono", "mobile", "celular", "contacto telefónico"]):
            return str(self.personal_info.get("phone_number", "906920958"))

        # 4. Correo / Email
        if any(k in label_lower for k in ["email", "correo", "e-mail"]):
            return str(self.personal_info.get("email", "pauloespinoza951@gmail.com"))

        # 5. Nombre / Apellidos
        if any(k in label_lower for k in ["first name", "primer nombre", "nombres"]):
            return str(self.personal_info.get("first_name", "Paulo Daniel"))
        if any(k in label_lower for k in ["last name", "apellidos", "apellido"]):
            return str(self.personal_info.get("last_name", "Espinoza Gamboa"))
        if any(k in label_lower for k in ["full name", "nombre completo"]):
            return str(self.personal_info.get("full_name", "Paulo Daniel Espinoza Gamboa"))

        # 6. Ciudad / Ubicación / Residencia
        if any(k in label_lower for k in ["city", "ciudad", "location", "ubicación", "ubicacion", "distrito", "país", "country"]):
            return str(self.personal_info.get("city", "Lima"))

        # 7. LinkedIn URL
        if "linkedin" in label_lower:
            return str(self.personal_info.get("linkedin_url", "https://www.linkedin.com/in/paulo-espinoza9/"))

        # 8. GitHub / Repositorio URL (Solo si pide link/URL/repositorio explícitamente)
        if any(k in label_lower for k in ["github", "repositorio", "enlace a tu git", "url de git", "portfolio", "portafolio", "website", "sitio web"]):
            return str(self.personal_info.get("github_url", "https://github.com/paulollito29-sketch"))

        # 9. Otras preguntas de años / numéricas
        if input_type == "number" or any(k in label_lower for k in ["years", "años", "total", "cantidad"]):
            return "1"

        # Check en text mappings genéricos
        for key, val in self.text_mappings.items():
            if key in label_lower:
                return str(val)

        return None

    def resolve_dropdown(self, question_text: str, options: List[str]) -> Optional[str]:
        q_lower = question_text.lower().strip()
        user_email = self.personal_info.get("email", "").lower()
        user_phone = str(self.personal_info.get("phone_number", ""))

        # Filtrar opciones que sean solo placeholders vacíos
        valid_options = [
            opt for opt in options 
            if opt.strip() and not any(p in opt.lower() for p in ["selecciona", "select", "choose", "elige", "---", "please"])
        ]

        if not valid_options:
            return options[0] if options else None

        # 1. Email
        if any(k in q_lower for k in ["email", "correo", "e-mail"]):
            for opt in valid_options:
                if user_email and user_email in opt.lower():
                    return opt
                if "@" in opt:
                    return opt

        # 2. Teléfono / Código de país
        if any(k in q_lower for k in ["phone", "teléfono", "telefono", "móvil", "movil", "mobile", "country code", "código"]):
            for opt in valid_options:
                if "+51" in opt or "peru" in opt.lower() or "perú" in opt.lower() or (user_phone and user_phone in opt):
                    return opt
            for opt in valid_options:
                if any(char.isdigit() for char in opt):
                    return opt

        # 3. Idioma inglés (Elegir SIEMPRE el nivel más alto: Avanzado / C1 / Intermedio, NUNCA Ninguno)
        if any(k in q_lower for k in ["english", "inglés", "ingles"]):
            prioritized = [
                "avanzado", "c1", "c2", "professional", "proficient", "fluent", "alto", "bilingüe", "bilingual",
                "intermedio alto", "b2", "intermedio", "intermediate", "conversacional", "conversational", "básico"
            ]
            for p in prioritized:
                for opt in valid_options:
                    if p in opt.lower():
                        return opt

        # 4. Disponibilidad / Comienzo inmediato / Disponibilidad horaria
        if any(k in q_lower for k in ["disponibilidad", "inmediat", "availability", "immediate", "empieces", "incorporaci"]):
            for opt in valid_options:
                if any(k in opt.lower() for k in ["inmediata", "si", "sí", "yes", "inmediato", "full"]):
                    return opt

        # 5. Educación / Grado
        if any(k in q_lower for k in ["education", "educación", "educacion", "degree", "grado", "estudios", "nivel"]):
            desired = ["bachelor", "universit", "college", "undergraduate", "estudiante", "en curso", "técnico", "superior", "bachiller"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 6. Experiencia / Años
        if any(k in q_lower for k in ["years", "años", "experience", "experiencia"]):
            desired = ["1", "0-1", "1-2", "1 year", "1 año", "menos de 1", "junior", "entry"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 7. Si las opciones son Sí / No
        if any(o.lower().strip() in ["yes", "no", "sí", "si"] for o in valid_options):
            return self.resolve_boolean_question(question_text, valid_options)

        # Evitar elegir opciones negativas como "Ninguno", "No", "None" si hay otras
        non_negative = [opt for opt in valid_options if not any(neg in opt.lower() for neg in ["ninguno", "none", "no cuenta"])]
        if non_negative:
            return non_negative[0]

        return valid_options[0]

    def resolve_boolean_question(self, question_text: str, option_texts: List[str]) -> Optional[str]:
        q_lower = question_text.lower().strip()
        
        # Buscar en reglas de preguntas booleanas
        target_bool = True # por defecto asumir respuesta positiva para calificaciones/autorizaciones
        for key, answer in self.boolean_questions.items():
            if key in q_lower:
                target_bool = answer
                break

        # Coincidencia con las opciones textuales
        yes_keywords = ["yes", "sí", "si", "true", "correcto", "autorizado", "dispuesto", "i am", "estoy de acuerdo", "agree"]
        no_keywords = ["no", "false", "falso", "ninguno", "none", "no requiero", "disagree"]

        for opt in option_texts:
            opt_lower = opt.strip().lower()
            if target_bool:
                if opt_lower in ["yes", "sí", "si"] or any(yk in opt_lower for yk in yes_keywords):
                    return opt
            else:
                if opt_lower in ["no"] or any(nk in opt_lower for nk in no_keywords):
                    return opt

        return option_texts[0] if option_texts else None

    def resolve_dropdown(self, question_text: str, options: List[str]) -> Optional[str]:
        q_lower = question_text.lower().strip()
        user_email = self.personal_info.get("email", "").lower()
        user_phone = str(self.personal_info.get("phone_number", ""))

        # Filtrar opciones que sean solo placeholders vacíos
        valid_options = [
            opt for opt in options 
            if opt.strip() and not any(p in opt.lower() for p in ["selecciona", "select", "choose", "elige", "---", "please"])
        ]

        if not valid_options:
            return options[0] if options else None

        # 1. Si el dropdown es de Email (seleccionar correo guardado en cuenta)
        if any(k in q_lower for k in ["email", "correo", "e-mail"]):
            for opt in valid_options:
                if user_email and user_email in opt.lower():
                    return opt
                if "@" in opt:
                    return opt

        # 2. Si el dropdown es de Teléfono (seleccionar número guardado en cuenta)
        if any(k in q_lower for k in ["phone", "teléfono", "telefono", "móvil", "movil", "mobile"]):
            for opt in valid_options:
                if user_phone and user_phone in opt:
                    return opt
                if "+51" in opt or any(char.isdigit() for char in opt):
                    return opt

        # 3. Código de país (+51 / Perú)
        if any(k in q_lower for k in ["country code", "código de país", "codigo", "country"]):
            for opt in valid_options:
                if "+51" in opt or "peru" in opt.lower() or "perú" in opt.lower():
                    return opt

        # 4. Idioma inglés
        if any(k in q_lower for k in ["english", "inglés", "ingles"]):
            desired = ["professional", "avanzado", "c1", "fluent", "proficient", "intermediate", "intermedio", "conversational", "alto"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 5. Idioma español
        if any(k in q_lower for k in ["spanish", "español", "espanol"]):
            desired = ["native", "nativo", "bilingual", "bilingüe", "fluent", "materno"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 6. Educación / Grado
        if any(k in q_lower for k in ["education", "educación", "educacion", "degree", "grado", "estudios", "nivel"]):
            desired = ["bachelor", "universit", "college", "undergraduate", "estudiante", "en curso", "técnico", "superior", "bachiller"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 7. Experiencia / Años
        if any(k in q_lower for k in ["years", "años", "experience", "experiencia"]):
            desired = ["1", "0-1", "1-2", "1 year", "1 año", "menos de 1", "junior", "entry"]
            for d in desired:
                for opt in valid_options:
                    if d in opt.lower():
                        return opt

        # 8. Si las opciones son Sí / No
        if any(o.lower().strip() in ["yes", "no", "sí", "si"] for o in valid_options):
            return self.resolve_boolean_question(question_text, valid_options)

        # Retornar la primera opción válida que no sea placeholder
        return valid_options[0]
