from module.campaign.campaign_base import CampaignBase
from module.campaign.run import CampaignRun
from module.combat.level import LevelOcr
from module.equipment.assets import *
from module.equipment.equipment_change import EquipmentChange
from module.equipment.fleet_equipment import OCR_FLEET_INDEX
from module.logger import logger
from module.map.assets import FLEET_PREPARATION, MAP_PREPARATION
from module.ocr.ocr import Digit
from module.retire.dock import *
from module.ui.page import page_fleet, page_main
from module.exception import CampaignEnd

SIM_VALUE = 0.95


class GemsCampaignOverride(CampaignBase):

    def handle_combat_low_emotion(self):
        '''
        Overwrite info_handler.handle_combat_low_emotion()
        If GEMS_LOW_EMOTION_WITHDRAW is True, withdraw combat and change flag ship
        '''
        if self.config.GEMS_LOW_EMOTION_WITHDRAW:
            if not self.config.IGNORE_LOW_EMOTION_WARN:
                return False
            if self.handle_popup_cancel('IGNORE_LOW_EMOTION'):
                self.config.GEMS_EMOTION_TRIGGRED = True
                logger.hr('EMOTION WITHDRAW')

                while 1:
                    self.device.screenshot()

                    if self.handle_popup_cancel('IGNORE_LOW_EMOTION'):
                        continue

                    if self.is_in_map():
                        self.withdraw()
                        break

                    if self.appear(FLEET_PREPARATION, offset=(20, 20), interval=2) or self.appear(MAP_PREPARATION, offset=(20, 20), interval=2):
                        self.enter_map_cancel()
                        break
                raise CampaignEnd('Emotion withdraw')
        else:
            return super().handle_combat_low_emotion()


class GemsFarming(CampaignRun, EquipmentChange):

    def load_campaign(self, name, folder='campaign_main'):
        super().load_campaign(name, folder)

        class GemsCampaign(GemsCampaignOverride, self.module.Campaign):
            pass

        self.campaign = GemsCampaign(device=self.campaign.device, config=self.campaign.config)

    def _fleet_detail_enter(self):
        '''
        Enter GEMS_FLEET_1 page
        '''
        self.ui_ensure(page_fleet)
        self.ui_ensure_index(self.config.GEMS_FLEET_1, letter=OCR_FLEET_INDEX,
                             next_button=FLEET_NEXT, prev_button=FLEET_PREV, skip_first_screenshot=True)

    def _ship_detail_enter(self, button):
        self._fleet_detail_enter()
        self.equip_enter(button)

    def flagship_change(self):
        '''
        Change flagship and flagship's equipment 
        If config.COMMON_CV_NAME == 'any', only change auxiliary equipment
        '''

        if self.config.COMMON_CV_NAME == 'any':
            index_list = range(3, 5)
        else:
            index_list = range(0, 5)
        logger.hr('CHANGING FLAGSHIP.')
        if self.config.GEMS_FLAG_SHIP_EQUIP_CHANGE:
            logger.info('Record flagship equipment.')
            self._ship_detail_enter(FLEET_ENTER_FLAGSHIP)
            self.record_equipment(index_list=index_list)
            self._equip_take_off_one()

        self._fleet_detail_enter()

        self.flagship_change_execute()

        if self.config.GEMS_FLAG_SHIP_EQUIP_CHANGE:
            logger.info('Record flagship equipment.')
            self._ship_detail_enter(FLEET_ENTER_FLAGSHIP)
            self._equip_take_off_one()

            self.equipment_take_on(index_list=index_list)

        self.ui_ensure(page_main)

    def vanguard_change(self):
        '''
        Change vanguard and vanguard's equipment 
        '''
        logger.hr('CHANGING VANGUARD.')
        if self.config.GEMS_VANGUARD_SHIP_EQUIP_CHANGE:
            logger.info('Record vanguard equipment.')
            self._ship_detail_enter(FLEET_ENTER)
            self.record_equipment()
            self._equip_take_off_one()

        self._fleet_detail_enter()

        self.vanguard_change_execute()

        if self.config.GEMS_VANGUARD_SHIP_EQUIP_CHANGE:
            logger.info('Equip vanguard equipment.')
            self._ship_detail_enter(FLEET_ENTER)
            self._equip_take_off_one()

            self.equipment_take_on()
        self.ui_ensure(page_main)

    def _ship_change_confirm(self, button):

        self.dock_select_one(button)
        self.dock_filter_set_faster()
        self.dock_select_confirm(check_button=page_fleet.check_button)

    def get_common_rarity_cv(self):
        """
        Get a common rarity cv by config.COMMON_CV_NAME
        If config.COMMON_CV_NAME == 'any', return a common lv1 cv
        Returns:
            Button:
        """

        level_grids = CARD_LEVEL_GRIDS
        card_grids = CARD_GRIDS
        logger.hr('FINDING FLAGSHIP')

        if self.config.COMMON_CV_NAME == 'any':
            logger.info('')

            self.dock_sort_method_dsc_set(False)

            level_ocr = LevelOcr(level_grids.buttons,
                                 name='DOCK_LEVEL_OCR', threshold=64)
            list_level = level_ocr.ocr(self.device.image)
            for button, level in list(zip(card_grids.buttons, list_level))[::-1]:
                if level == 1:
                    return button

            return None
        else:
            template = globals()[
                f'TEMPLATE_{self.config.COMMON_CV_NAME.upper()}']

            self.dock_sort_method_dsc_set()

            ocr = LevelOcr(level_grids.buttons, name='DOCK_LEVEL_OCR')
            list_level = ocr.ocr(self.device.image)

            for button, level in zip(card_grids.buttons, list_level):
                if level == 1 and template.match(self.device.image.crop(button.area), similarity=SIM_VALUE):
                    return button

            logger.info('No specific CV was found, try reversed order.')
            self.dock_sort_method_dsc_set(False)

            list_level = ocr.ocr(self.device.image)

            for button, level in zip(card_grids.buttons, list_level):
                if level == 1 and template.match(self.device.image.crop(button.area), similarity=SIM_VALUE):
                    return button

            return None

    def get_common_rarity_dd(self):
        """
        Get a common rarity dd with level is 100 and emotion is 150
        Returns:
            Button:
        """
        logger.hr('FINDING VANGUARD')

        level_grids = CARD_LEVEL_GRIDS
        card_grids = CARD_GRIDS
        emotion_grids = CARD_EMOTION_GRIDS

        level_ocr = LevelOcr(level_grids.buttons,
                             name='DOCK_LEVEL_OCR', threshold=64)
        list_level = level_ocr.ocr(self.device.image)
        emotion_ocr = Digit(emotion_grids.buttons,
                            name='DOCK_EMOTION_OCR', threshold=176)
        list_emotion = emotion_ocr.ocr(self.device.image)

        for button, level, emotion in list(zip(card_grids.buttons, list_level, list_emotion))[::-1]:
            if level == 100 and emotion == 150:
                return button

        return None

    def flagship_change_execute(self):
        """
        Returns:
            bool: If success.

        Pages:
            in: page_fleet
            out: page_fleet
        """
        self.ui_click(FLEET_ENTER_FLAGSHIP,
                      appear_button=page_fleet.check_button, check_button=DOCK_CHECK, skip_first_screenshot=True)
        self.dock_filter_set_faster(
            index='cv', rarity='common', extra='enhanceable', sort='total')
        self.dock_favourite_set(False)

        self.device.screenshot()
        ship = self.get_common_rarity_cv()
        if ship is not None:
            self._ship_change_confirm(ship)

            logger.info('Change flagship success')
            return True
        else:
            logger.info('Change flagship failed, no CV in common rarity.')
            self.dock_filter_set_faster()
            self.ui_back(check_button=page_fleet.check_button)
            return False

    def vanguard_change_execute(self):
        """
        Returns:
            bool: If success.

        Pages:
            in: page_fleet
            out: page_fleet
        """
        self.ui_click(FLEET_ENTER,
                      appear_button=page_fleet.check_button, check_button=DOCK_CHECK, skip_first_screenshot=True)
        self.dock_filter_set_faster(
            index='dd', rarity='common', faction='eagle')
        self.dock_favourite_set(False)

        self.device.screenshot()
        ship = self.get_common_rarity_dd()
        if ship is not None:
            self._ship_change_confirm(ship)

            logger.info('Change vanguard ship success')
            return True
        else:
            logger.info('Change vanguard ship failed, no DD in common rarity.')
            self.dock_filter_set_faster()
            self.ui_back(check_button=page_fleet.check_button)
            return False

    _trigger_lv32 = False
    _trigger_emotion = False

    def triggered_stop_condition(self, oil_check=True):
        # Lv32 limit
        if self.config.STOP_IF_REACH_LV32 and self.campaign.config.LV32_TRIGGERED:
            self._trigger_lv32 = True
            logger.hr('TRIGGERED LV32 LIMIT')
            return True

        if self.config.ENABLE_AUTO_SEARCH and self.campaign.config.GEMS_EMOTION_TRIGGRED:
            self._trigger_emotion = True
            logger.hr('TRIGGERED EMOTION LIMIT')
            return True

        return super().triggered_stop_condition(oil_check=oil_check)

    def run(self, name, folder='campaign_main', total=0):
        name = name.lower()
        if not name[0].isdigit():
            folder = self.config.EVENT_NAME
        else:
            name = 'campaign_' + name.replace('-', '_')

        while 1:
            # Backup config file
            # will cover ENABLE_AUTO_SEARCH
            backup = self.config.cover(
                STOP_IF_REACH_LV32=True,
                FLEET_1=self.config.GEMS_FLEET_1,
                FLEET_2=self.config.GEMS_FLEET_2,
                FLEET_BOSS=1,
                SUBMARINE=0,
                FLEET_1_FORMATION=1,
                FLEET_2_FORMATION=1,
                FLEET_1_AUTO_MODE='combat_auto',
                FLEET_2_AUTO_MODE='combat_auto',
                ENABLE_MAP_FLEET_LOCK=True,
                ENABLE_2X_BOOK=False,
                STOP_IF_MAP_REACH='no',
                ENABLE_EMOTION_REDUCE=False,
                IGNORE_LOW_EMOTION_WARN=True,
                AUTO_SEARCH_SETTING='fleet1_all_fleet2_standby',
                ENABLE_AUTO_SEARCH=self.config.GEMS_ENABLE_AUTO_SEARCH,
                RETIRE_KEEP_COMMON_CV=True,
            )
            self._trigger_lv32 = False

            try:
                super().run(name=name, folder=folder, total=total)
            except CampaignEnd as e:
                if e.args[0] == 'Emotion withdraw':
                    self._trigger_emotion = True
                else:
                    raise e

            # End
            if self._trigger_lv32 or self._trigger_emotion:
                self.flagship_change()

                if self.config.GEMS_LOW_EMOTION_WITHDRAW:
                    self.vanguard_change()

                self._trigger_lv32 = False
                self._trigger_emotion = False
                self.campaign.config.LV32_TRIGGERED = False
                self.campaign.config.GEMS_EMOTION_TRIGGRED = False
                continue
            else:
                backup.recover()
                break
