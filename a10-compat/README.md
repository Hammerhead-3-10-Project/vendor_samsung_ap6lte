Android 10 keymaster support libraries, byte-identical to the stock A6+ system partition.

The stock `libkeymaster3device.so` / `android.hardware.keymaster@3.0-impl.so` link against the Android 10 ABI of these
libraries (e.g. `keymaster::EcdsaOperationFactory::CreateOperation(...) const`). The Android 11 builds (`*.vendor:32`) have a
different ABI, so the keymaster service failed with "cannot locate symbol" and system_server crashed without a keystore.
They are installed in /vendor/lib; the modules of the same name are no longer requested in the device tree.
