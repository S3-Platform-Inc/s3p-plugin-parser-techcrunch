import pytz
import dateparser
import time

from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


class Techcrunch(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """
    HOST = "https://techcrunch.com/category/fintech/"
    utc = pytz.UTC

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, web_driver: WebDriver, max_count_documents: int = None,
                 last_document: S3PDocument = None):
        super().__init__(refer, plugin, max_count_documents, last_document)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -
        self._initial_access_source("https://techcrunch.com/category/fintech/")
        self._wait.until(ec.presence_of_element_located((By.XPATH, "//*[contains(@class,'loop-card__content')]")))
        time.sleep(3)
        while True:

            self.logger.debug('Загрузка списка элементов...')
            doc_table = self._driver.find_elements(By.XPATH,
                                                   "//div[contains(@class,'wp-block-query is-layout-flow wp-block-query-is-layout-flow has-rapid-read has-loaded-user')]//div[contains(@class,'loop-card__content')]")
            self.logger.debug('Обработка списка элементов...')

            for i, element in enumerate(doc_table):
                self.logger.debug(doc_table[i].text)

            for i, element in enumerate(doc_table):
                try:
                    title = doc_table[i].find_element(By.XPATH, ".//h3[contains(@class,'loop-card__title')]").text
                except:
                    self.logger.exception('Не удалось извлечь title')
                    continue
                other_data = None

                try:
                    web_link = doc_table[i].find_element(By.XPATH,
                                                         ".//h3[contains(@class,'loop-card__title')]").find_element(
                        By.TAG_NAME,
                        'a').get_attribute(
                        'href')
                except:
                    self.logger.exception('Не удалось извлечь web_link, пропущен')
                    continue

                self._driver.execute_script("window.open('');")
                self._driver.switch_to.window(self._driver.window_handles[1])
                self._driver.get(web_link)
                time.sleep(3)

                try:
                    abstract = self._driver.find_element(By.ID, 'speakable-summary').text
                except:
                    self.logger.exception('Не удалось извлечь abstract')
                    abstract = None

                try:
                    pub_date = dateparser.parse(self._driver.find_element(By.XPATH,
                                                                          "//div[contains(@class,'wp-block-post-date')]/time").get_attribute(
                        'datetime'))
                except:
                    self.logger.exception('Не удалось извлечь pub_date')
                    continue

                try:
                    text_content = self._driver.find_element(By.XPATH,
                                                             "//div[contains(@class, 'entry-content')]").text
                except:
                    self.logger.exception('Не удалось извлечь text_content')
                    text_content = None

                document = S3PDocument(
                    id=None,
                    title=title,
                    abstract=abstract,
                    text=text_content,
                    link=web_link,
                    storage=None,
                    other=other_data,
                    published=pub_date,
                    loaded=None,
                )
                self._find(document)
                self._driver.close()
                self._driver.switch_to.window(self._driver.window_handles[0])

            try:
                # // *[ @ id = "all-materials"] / font[2] / a[5]
                pagination_arrow = self._driver.find_element(By.XPATH, "//a/span[contains(text(),'Next')]/..")
                pg_num = pagination_arrow.get_attribute('href')
                self._driver.execute_script('arguments[0].click()', pagination_arrow)
                time.sleep(3)
                self.logger.info(f'Выполнен переход на след. страницу: {pg_num}')
            except:
                raise NoSuchElementException('Не удалось найти переход на след. страницу. Прерывание цикла обработки')

    def _initial_access_source(self, url: str, delay: int = 2):
        self._driver.get(url)
        self.logger.debug('Entered on web page ' + url)
        time.sleep(delay)
        # self._agree_cookie_pass()

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_xpath = '//*[@id="onetrust-accept-btn-handler"]'

        try:
            cookie_button = self._driver.find_element(By.XPATH, cookie_agree_xpath)
            if WebDriverWait(self._driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self._driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self._driver.current_url}')
