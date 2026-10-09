"""Subjects and topics for the demo curriculum (KSSM Form 4/5 aligned)."""

SUBJECTS = [
    # code, name, icon, color, description
    ("BM", "Bahasa Melayu", "languages", "rose", "Tatabahasa, karangan dan pemahaman."),
    ("ENG", "English", "book-open", "sky", "Grammar, reading and writing skills."),
    ("MATH", "Mathematics", "calculator", "violet", "Core SPM Mathematics."),
    ("ADDMATH", "Additional Mathematics", "sigma", "indigo", "Calculus, functions and progressions."),
    ("PHY", "Physics", "atom", "cyan", "Forces, motion and electricity."),
    ("CHEM", "Chemistry", "flask-conical", "emerald", "Matter, bonding and reactions."),
    ("BIO", "Biology", "leaf", "lime", "Cells, organisms and life processes."),
    ("HIST", "History", "landmark", "amber", "Sejarah Malaysia and world history."),
    ("GEO", "Geography", "globe", "teal", "Physical and human geography."),
    ("MORAL", "Pendidikan Moral", "heart-handshake", "pink", "Values for life in a diverse society."),
]

TOPICS = [
    # key, subject code, name, form, description
    ("quadratic", "MATH", "Quadratic Equations", 4, "Standard form, factorisation and solving ax² + bx + c = 0."),
    ("linear", "MATH", "Linear Equations", 4, "Solving linear equations and simultaneous equations."),
    ("functions", "MATH", "Functions", 4, "Function notation, inverse and composite functions."),
    ("trigonometry", "MATH", "Trigonometry", 4, "Sine, cosine and tangent in right-angled triangles."),
    ("statistics", "MATH", "Statistics", 4, "Mean, median, mode and range of data."),
    ("indices", "MATH", "Indices", 4, "Laws of indices and simplifying powers."),
    ("differentiation", "ADDMATH", "Differentiation", 5, "Gradients and the power rule."),
    ("progressions", "ADDMATH", "Arithmetic Progressions", 5, "nth term and sum of an arithmetic progression."),
    ("electricity", "PHY", "Electricity", 5, "Current, voltage, resistance and power."),
    ("forces", "PHY", "Forces and Motion", 4, "Velocity, acceleration, momentum and Newton's laws."),
    ("mole", "CHEM", "The Mole Concept", 4, "Relating mass, moles and number of particles."),
    ("bonding", "CHEM", "Chemical Bonding", 4, "Ionic and covalent bonds."),
    ("cell", "BIO", "Cell Biology", 4, "Cell structure, organelles and their functions."),
    ("independence", "HIST", "Road to Independence", 4, "Key events leading to Merdeka and the formation of Malaysia."),
    ("tenses", "ENG", "Grammar: Tenses", 4, "Using present, past and future tenses correctly."),
    ("imbuhan", "BM", "Tatabahasa: Imbuhan", 4, "Awalan, akhiran, apitan dan sisipan."),
    ("climate", "GEO", "Weather and Climate", 4, "Elements of weather and Malaysia's climate."),
    ("values", "MORAL", "Values in Society", 4, "Responsibility, respect and harmony."),
]
