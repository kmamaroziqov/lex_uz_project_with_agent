import logging
from app.interfaces.agent_interface import AbstractAgentService
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AgentService(AbstractAgentService):
    def __init__(self, db_repository=None) -> None:
        self._settings = get_settings()
        self._db_repo = db_repository
        self._setup_llm_config()

    def _setup_llm_config(self) -> None:
        import autogen

        self._config_list = [
            {
                "base_url": self._settings.OLLAMA_BASE_URL,
                "model": self._settings.OLLAMA_MODEL,
                "api_key": "ollama",
                "price": [0, 0],  # No cost for local models
            }
        ]
        self._client = autogen.OpenAIWrapper(config_list=self._config_list)

    def classify_intent(self, question: str) -> str:
        try:
            prompt = (
                f'Savol: "{question}"\n\n'
                "Quyidagi kategoriyalardan FAQAT BITTASINI qaytaring:\n"
                "SOCIAL  — salomlashish, tanishish yoki bot haqida savol\n"
                "LEGAL   — qonun, modda, huquq, jazo, jinoyat, shartnoma, sud, "
                "konstitutsiya, kodeks, nizom, javobgarlik, huquqiy maslahat\n"
                "UNKNOWN — boshqa barcha mavzular (ob-havo, tarix, sport, ovqat va h.k.)\n\n"
                "Faqat bitta so'z: SOCIAL, LEGAL yoki UNKNOWN"
            )
            res = self._client.create(messages=[{"role": "user", "content": prompt}])
            intent = res.choices[0].message.content.strip().upper()
            result = intent if intent in {"SOCIAL", "LEGAL", "UNKNOWN"} else "LEGAL"
            logger.info("classify_intent | intent=%s", result)
            return result
        except Exception as exc:
            logger.warning("classify_intent failed: %s", exc)
            return "LEGAL"

    async def get_response(self, question: str, history: str) -> str:
        intent = self.classify_intent(question)
        if intent == "UNKNOWN":
            return (
                "Men faqat O'zbekiston Respublikasi qonunchiligi bo'yicha "
                "huquqiy savollarga javob bera olaman. "
                "Iltimos, huquqiy mavzuda savol bering."
            )
        elif intent == "SOCIAL":
            return self._handle_social(question, history)
        else:
            return await self._run_legal_pipeline(question, history)

    def _rewrite_query(self, question: str, history: str) -> str:
        if not history or len(question.split()) > 7:
            return question
        try:
            prompt = (
                f"Suhbat tarixi:\n{history}\n\n"
                f'Oxirgi savol: "{question}"\n\n'
                "QOIDA: Agar savol qisqa anafora bo'lsa ('Jazosi?', 'Nima deyilgan?', 'Unda?'), "
                "uni tarixdagi oxirgi mavzuga ulab to'liq qidiruv so'roviga aylantir. "
                "Agar savol mustaqil bo'lsa — aynan o'zini qaytargin. "
                "Faqat savol matnini qaytargin."
            )
            res = self._client.create(messages=[{"role": "user", "content": prompt}])
            rewritten = res.choices[0].message.content.strip().strip('"')
            if 5 <= len(rewritten) <= 400:
                return rewritten
        except Exception as exc:
            logger.warning("_rewrite_query failed: %s", exc)
        return question

    def _direct_search(self, query: str) -> str:
        try:
            if self._db_repo:
                return self._db_repo.format_search_results(query)
            else:
                from database import search_lexuz_tool
                return search_lexuz_tool(query) or ""
        except Exception as exc:
            logger.error("_direct_search failed: %s", exc)
            return ""

    def _handle_social(self, question: str, history: str) -> str:
        system_msg = (
            "Siz LexAI — O'zbekiston Respublikasi qonunchiligi bo'yicha "
            "ixtisoslashgan professional huquqiy yordamchisiz.\n"
            "QOIDALAR:\n"
            "1. Birinchi murojaat bo'lsa: qisqacha salom bering va o'zingizni tanishtiring.\n"
            "2. Keyingi murojaatlarda 'Salom' YOZMANG, to'g'ri javob bering.\n"
            "3. Foydalanuvchini huquqiy savol berishga yo'naltiring.\n"
            "4. Qisqa va aniq javob bering."
        )
        messages = [{"role": "system", "content": system_msg}]
        if history:
            messages.append({"role": "assistant", "content": f"Oldingi suhbat:\n{history}"})
        messages.append({"role": "user", "content": question})
        try:
            res = self._client.create(messages=messages)
            return res.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("_handle_social failed: %s", exc)
            return "Salom! Men LexAI — huquqiy yordamchiman. Huquqiy savolingizni bering."

    def _analyze_results(self, query: str, raw_results: str) -> str:
        has_results = raw_results and "TASDIQLANGAN MANBALAR" in raw_results

        if has_results:
            task_instruction = (
                "Yuqoridagi TASDIQLANGAN MANBALAR asosida professional huquqiy javob bering.\n\n"
                "JAVOB FORMATI QO'YDALAR:\n"
                "1. Agar manba muayyan moddaga to'g'ridan-to'g'ri ishora qilsa:\n"
                "   [Qonun nomi] — [Modda №] — [Qisqa mazmun] — [Jazo/oqibat]\n"
                "2. Agar savol tushuntirish yoki tahlil talab qilsa (masalan, 'qanday qilib', "
                "'nima qilsam', 'qaysi jazo og'ir'):\n"
                "   Moddalarni sanab o'tirmay, ANIQ va TUSHUNARLI izohlab bering.\n"
                "   Tegishli moddalarni faqat ular haqiqatan ham savolga javob bergandagina qo'shing.\n"
                "3. Faqat manbalardagi ma'lumotdan foydalaning. O'zingizdan modda o'ylab qo'shmang.\n"
                "4. Bir savolga bir nechta aloqasiz moddalarni tiqishtirmang."
            )
        else:
            task_instruction = (
                "Bazada aniq ma'lumot topilmadi. "
                "O'zbekiston qonunchiligi bo'yicha UMUMIY bilimingizdan "
                "qisqa va aniq javob bering. "
                "Javob oxirida: 'Aniq huquqiy maslahat uchun "
                "malakali huquqshunos bilan bog'laning.' qo'shing."
            )

        prompt = (
            f'Foydalanuvchi savoli: "{query}"\n\n'
            f"{'Topilgan manbalar:\n' + raw_results if has_results else 'Bazada natija topilmadi.'}\n\n"
            f"{task_instruction}\n\n"
            "UMUMIY QOIDALAR:\n"
            "• 'Salom', 'Albatta', 'Rahmat', 'Keling ko'rib chiqaylik' kabi so'zlar YOZMANG\n"
            "• Faqat savol uchun zarur bo'lgan moddalarni keltiring, barchani emas\n"
            "• Javobni o'zbek tilida, aniq va professional tarzda bering\n"
            "• Keraksiz takrorlardan saqlaning"
        )
        try:
            res = self._client.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Siz O'zbekiston Respublikasi qonunchiligi bo'yicha "
                            "20 yillik tajribaga ega professional huquqshunossiz."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            return res.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("_analyze_results failed: %s", exc)
            return "Texnik xato yuz berdi. Iltimos qayta urinib ko'ring."

    async def _run_legal_pipeline(self, question: str, history: str) -> str:
        query = self._rewrite_query(question, history)
        logger.info("_run_legal_pipeline | query=%r", query[:80])
        raw = self._direct_search(query)
        found = bool(raw and "TASDIQLANGAN MANBALAR" in raw)
        logger.info("_run_legal_pipeline | db_hit=%s", found)
        return self._analyze_results(query, raw)
