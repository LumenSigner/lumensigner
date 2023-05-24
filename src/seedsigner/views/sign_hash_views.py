import binascii
import logging
import re
from dataclasses import dataclass

from stellar_sdk import Keypair

from seedsigner.controller import Controller
from seedsigner.gui.components import (
    FontAwesomeIconConstants,
    SeedSignerCustomIconConstants,
    TextArea,
    GUIConstants,
)
from seedsigner.gui.screens.screen import (
    RET_CODE__BACK_BUTTON,
    ButtonListScreen,
    DireWarningScreen,
    QRDisplayScreen,
)
from .view import BackStackView, View, Destination, MainMenuView
from ..models import EncodeQR, QRType

logger = logging.getLogger(__name__)


class SignHashSelectSeedView(View):
    def run(self, **kwargs):
        seeds = self.controller.storage.seeds
        SCAN_SEED = ("Scan a seed", FontAwesomeIconConstants.QRCODE)
        TYPE_12WORD = ("Enter 12-word seed", FontAwesomeIconConstants.KEYBOARD)
        TYPE_24WORD = ("Enter 24-word seed", FontAwesomeIconConstants.KEYBOARD)
        button_data = [
            (seed.get_fingerprint(), SeedSignerCustomIconConstants.FINGERPRINT, "blue")
            for seed in seeds
        ]
        button_data += [SCAN_SEED, TYPE_12WORD, TYPE_24WORD]

        selected_menu_num = ButtonListScreen(
            title="Select Signer",
            is_button_text_centered=False,
            button_data=button_data,
        ).display()

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if len(seeds) > 0 and selected_menu_num < len(seeds):
            # User selected one of the n seeds
            self.controller.sign_seed = self.controller.get_seed(selected_menu_num)
            address_index = parse_address_index_from_derivation_path(
                self.controller.sign_hash_data[0]
            )
            sign_kp = Keypair.from_mnemonic_phrase(
                mnemonic_phrase=self.controller.sign_seed.mnemonic_str,
                passphrase=self.controller.sign_seed.passphrase,
                index=address_index,
            )

            return Destination(SignHashDireWarningView, view_args={"sign_kp": sign_kp})

        # The remaining flows are a sub-flow; resume sign hash flow once the seed is loaded.
        self.controller.resume_main_flow = Controller.FLOW__SIGN_HASH

        if button_data[selected_menu_num] == SCAN_SEED:
            from seedsigner.views.scan_views import ScanView

            return Destination(ScanView)

        elif button_data[selected_menu_num] in [TYPE_12WORD, TYPE_24WORD]:
            from seedsigner.views.seed_views import SeedMnemonicEntryView

            if button_data[selected_menu_num] == TYPE_12WORD:
                self.controller.storage.init_pending_mnemonic(num_words=12)
            else:
                self.controller.storage.init_pending_mnemonic(num_words=24)
            return Destination(SeedMnemonicEntryView)


class SignHashDireWarningView(View):
    def __init__(self, sign_kp: Keypair = None):
        super().__init__()
        self.sign_kp = sign_kp

    def run(self, **kwargs):
        selected_menu_num = DireWarningScreen(
            title="Hash signing",
            status_headline="Dangerous operation!",
            text="You should only sign hashes if you know what you are doing.",
            show_back_button=True,
        ).display()

        if selected_menu_num == 0:
            # User clicked "I Understand"
            return Destination(
                SignHashShowAddressView, view_args={"sign_kp": self.sign_kp}
            )

        elif selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(MainMenuView)


@dataclass
class ToolsSignHashShowAddressScreen(ButtonListScreen):
    address: str = None

    def __post_init__(self):
        self.title = "Sign with"
        self.is_bottom_list = True

        super().__post_init__()

        break_point = 14
        # break every 14 characters
        address_with_break = " ".join(
            [
                self.address[i : i + break_point]
                for i in range(0, len(self.address), break_point)
            ]
        )

        self.components.append(
            TextArea(
                text=address_with_break,
                font_size=GUIConstants.BODY_FONT_MAX_SIZE + 1,
                font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
                screen_y=self.top_nav.height,
                is_text_centered=True,
            )
        )


class SignHashShowAddressView(View):
    def __init__(self, sign_kp: Keypair = None):
        super().__init__()
        self.sign_kp = sign_kp

    def run(self):
        CONTINUE = "Continue"
        ABORT = "Abort"
        button_data = [CONTINUE, ABORT]
        selected_menu_num = ToolsSignHashShowAddressScreen(
            address=self.sign_kp.public_key,
            button_data=button_data,
        ).display()

        print("selected_menu_num: ", selected_menu_num)

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == CONTINUE:
            return Destination(
                SignHashShowHashView, view_args={"sign_kp": self.sign_kp}
            )
        elif button_data[selected_menu_num] == ABORT:
            return Destination(MainMenuView)


@dataclass
class ToolsSignHashShowHashScreen(ButtonListScreen):
    hash: str = None

    def __post_init__(self):
        self.title = "Hash"
        self.is_bottom_list = True

        super().__post_init__()

        break_point = 16
        # break every 16 characters
        hash_with_break = " ".join(
            [
                self.hash[i : i + break_point]
                for i in range(0, len(self.hash), break_point)
            ]
        )

        self.components.append(
            TextArea(
                text=hash_with_break,
                font_size=GUIConstants.BODY_FONT_MAX_SIZE + 1,
                font_name=GUIConstants.FIXED_WIDTH_EMPHASIS_FONT_NAME,
                screen_y=self.top_nav.height,
                is_text_centered=True,
            )
        )


class SignHashShowHashView(View):
    def __init__(self, sign_kp: Keypair = None):
        super().__init__()
        self.sign_kp = sign_kp

    def run(self):
        SIGN = "Sign"
        ABORT = "Abort"
        button_data = [SIGN, ABORT]
        selected_menu_num = ToolsSignHashShowHashScreen(
            hash=self.controller.sign_hash_data[1],
            button_data=button_data,
        ).display()

        print("selected_menu_num: ", selected_menu_num)

        if selected_menu_num == RET_CODE__BACK_BUTTON:
            return Destination(BackStackView)

        if button_data[selected_menu_num] == SIGN:
            data = binascii.unhexlify(self.controller.sign_hash_data[1])
            signature = self.sign_kp.sign(data)
            qr_encoder = EncodeQR(qr_type=QRType.STELLAR_SIGNATURE, signature=signature)
            QRDisplayScreen(
                qr_encoder=qr_encoder,
            ).display()
            return Destination(MainMenuView)

        elif button_data[selected_menu_num] == ABORT:
            return Destination(MainMenuView)


def parse_address_index_from_derivation_path(derivation_path: str) -> int:
    regex = "m/44'\\/148'\\/(\\d+)'"
    matches = re.search(regex, derivation_path)
    if matches:
        return int(matches.group(1))
    raise ValueError(
        f"Could not parse address index from derivation path: {derivation_path}"
    )
