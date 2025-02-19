from datetime import datetime

from module.logger import logger
from module.os.config import OSConfig
from module.os.map_operation import OSMapOperation
from module.os.operation_siren import OperationSiren, RECORD_MISSION_ACCEPT, RECORD_SUPPLY_BUY, RECORD_MISSION_FINISH
from module.os.operation_siren import RECORD_OBSCURE_FINISH


class OSCampaignRun(OSMapOperation):
    campaign: OperationSiren

    campaign_loaded = False

    def load_campaign(self):
        if self.campaign_loaded:
            return False

        config = self.config.merge(OSConfig())
        self.campaign = OperationSiren(config=config, device=self.device)
        self.campaign.os_init()

        self.campaign_loaded = True
        return True

    def run(self):
        self.load_campaign()
        self.campaign.run()

    def run_operation_siren(self):
        self.load_campaign()
        self.campaign.operation_siren()

    def record_executed_since(self):
        mission = self.config.ENABLE_OS_MISSION_ACCEPT \
                  and not self.config.record_executed_since(option=RECORD_MISSION_ACCEPT, since=(0,))
        supply = self.config.ENABLE_OS_SUPPLY_BUY \
                 and not self.config.record_executed_since(option=RECORD_SUPPLY_BUY, since=(0,))
        finish = self.config.ENABLE_OS_MISSION_FINISH \
                 and not self.config.record_executed_since(option=RECORD_MISSION_FINISH, since=(0,))

        if mission or supply or finish:
            return False
        else:
            return True

    def run_daily(self):
        self.load_campaign()
        self.campaign.operation_siren_daily()

    def run_clear_os_world(self):
        self.load_campaign()
        self.campaign.clear_os_world()

    def os_obscure_next_run_reached(self):
        record = datetime.strptime(self.config.config.get(*RECORD_OBSCURE_FINISH), self.config.TIME_FORMAT)
        now = datetime.now().replace(microsecond=0)
        attr = '_'.join(RECORD_OBSCURE_FINISH)
        logger.attr(f'{attr}', f'Current time: {now}')
        logger.attr(f'{attr}', f'Next run: {record}')
        return now > record

    def run_obscure_clear(self):
        if not self.os_obscure_next_run_reached():
            return False

        self.load_campaign()
        self.campaign.os_obscure_finish()
