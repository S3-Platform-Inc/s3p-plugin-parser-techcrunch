from datetime import datetime
from typing import Iterator
import pytz
import time

from s3p_sdk.exceptions.parser import S3PPluginParserFinish, S3PPluginParserOutOfRestrictionException
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from s3p_sdk.types.plugin_restrictions import FROM_DATE
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

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, web_driver: WebDriver, restrictions: S3PPluginRestrictions):
        super().__init__(refer, plugin, restrictions)

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

        for page_link in self._infinity_page_links():
            # each page
            try:
                self._initial_access_source(page_link)
            except Exception as e:
                raise S3PPluginParserFinish(plugin=self._plugin, message='link can\'t open', errors=e)

            for post in self._page_links(page_link):
                try:
                    doc = self._document_from_page(post)
                except Exception as e:
                    self.logger.error(e)
                else:
                    try:
                        self._find(doc)
                    except S3PPluginParserOutOfRestrictionException as e:
                        if e.restriction == FROM_DATE:
                            self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
                            raise S3PPluginParserFinish(self._plugin,
                                                        f'Document is out of date range `{self._restriction.from_date}`', e)

    def _document_from_page(self, url: str) -> S3PDocument:
        self._initial_access_source(url)

        WebDriverWait(self._driver, 10).until(
            ec.presence_of_element_located((By.CLASS_NAME, 'article-hero'))
        )

        # Extract main elements
        title = self._driver.find_element(By.CSS_SELECTOR, 'h1.article-hero__title.wp-block-post-title').text
        published_date = datetime.fromisoformat(
            self._driver.find_element(By.CSS_SELECTOR, 'div.wp-block-post-date > time[datetime]').get_attribute('datetime')
        )

        # Extract article body
        article_body = self._driver.find_elements(By.CSS_SELECTOR, 'div.wp-block-post-content > p')
        text = '\n'.join([p.text for p in article_body]) if article_body else None

        # Abstract
        abstract = None
        meta_description = self._driver.find_elements(By.CSS_SELECTOR, 'meta[name="description"]')
        if meta_description:
            abstract = meta_description[0].get_attribute('content')
        elif article_body:
            abstract = article_body[0].text[:200] + '...'

        # author
        author_selector = (By.CSS_SELECTOR, 'meta[name="author"]')
        self._wait.until(
            ec.presence_of_element_located(
                author_selector
            )
        )
        category_selector = (By.CSS_SELECTOR, 'div.article-hero__category > a')
        self._wait.until(
            ec.presence_of_element_located(
                category_selector
            )
        )

        return S3PDocument(
            id=None,
            title=title,
            abstract=abstract,
            text=text,
            link=url,
            storage=None,
            other={
                'author': self._driver.find_element(*author_selector).text,
                'category': self._driver.find_element(*category_selector).text,
            },
            published=published_date.replace(tzinfo=None),
            loaded=datetime.now()
        )

    def _infinity_page_links(self) -> Iterator[str]:
        template = self.HOST + 'page/{page_number}/?guccounter=1'

        page_number = 1
        while True:
            yield template.format(page_number=page_number)
            page_number += 1

    def _page_links(self, url: str) -> list[str]:
        self._initial_access_source(url)

        doc_table = self._driver.find_elements(By.XPATH,"//div[contains(@class,'wp-block-query is-layout-flow wp-block-query-is-layout-flow has-rapid-read has-loaded-user')]//div[contains(@class,'loop-card__content')]")
        self._wait.until(ec.presence_of_element_located((By.XPATH, "//*[contains(@class,'loop-card__content')]")))

        post_links = []
        for i, post in enumerate(doc_table):
            web_link = post.find_element(By.XPATH,
                                                 ".//h3[contains(@class,'loop-card__title')]").find_element(
                By.TAG_NAME,
                'a').get_attribute(
                'href')
            post_links.append(web_link)

        return post_links

    def _initial_access_source(self, url: str, delay: int = 2):
        self._driver.get(url)
        self.logger.debug('Entered on web page ' + url)
        time.sleep(delay)
        self._agree_cookie_pass()

    def _agree_cookie_pass(self, timeout: int = 2):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_id = 'didomi-notice-disagree-button'

        try:
            cookie_button = self._driver.find_element(By.ID, cookie_agree_id)
            if WebDriverWait(self._driver, timeout).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self._driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self._driver.current_url}')
