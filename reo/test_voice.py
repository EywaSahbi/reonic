import voice


def test_spoken_units_money_and_abbreviations():
    s = voice.spoken
    assert s("About 8 kWp of solar with a 10 kWh battery.") == "About 8 kilowatt peak of solar with a 10 kilowatt hours battery."
    assert s("That would cost roughly €11,900–22,600 (estimate).") == "That would cost roughly 11,900 to 22,600 euros (estimate)."
    assert s("around €1,530 a year instead of €2,110") == "around 1,530 euros a year instead of 2,110 euros"
    assert s("cut your heating CO₂ by about 53%") == "cut your heating carbon dioxide by about 53 percent"
    assert s("a 48 m² roof, 8 x 6 m, 3.7× less") == "a 48 square metres roof, 8 by 6 m, 3.7 times less"
    assert s("You have an EV, ~11 kW wallbox, 1,900 kg/yr") == "You have an E V, about 11 kilowatts wallbox, 1,900 kilograms per year"
    assert s("Payback in 10–11 yrs, e.g. 35 ct") == "Payback in 10 to 11 years, for example 35 cents"
