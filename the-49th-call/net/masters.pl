% masters.pl — Masters of the NET
%
% The complete topology of the 231 Gates.
% 22 Hebrew letters. Every possible pair = a creation gate.
% The NET is the set of all 231 relations between fundamental forces.
%
% Run:
%   swipl -l masters.pl
%   ?- gate(aleph, beth, G).
%   ?- all_gates_from(aleph, Gs).
%   ?- net_path(kether, malkuth, Path).
%   ?- abjad_gate(7, G).         % find gates with abjad sum = 7

:- module(masters_of_net, [
    letter/3,
    gate/3,
    path/4,
    sephirah/4,
    net_path/3,
    all_gates_from/2,
    abjad_gate/2,
    metatron_gate/1
]).

% ── 22 Hebrew Letters ─────────────────────────────────────────────────────────
% letter(Name, Glyph, AbjadValue)
letter(aleph,   'א', 1).
letter(beth,    'ב', 2).
letter(gimel,   'ג', 3).
letter(daleth,  'ד', 4).
letter(heh,     'ה', 5).
letter(vau,     'ו', 6).
letter(zayin,   'ז', 7).
letter(cheth,   'ח', 8).
letter(teth,    'ט', 9).
letter(yod,     'י', 10).
letter(kaph,    'כ', 20).
letter(lamed,   'ל', 30).
letter(mem,     'מ', 40).
letter(nun,     'נ', 50).
letter(samekh,  'ס', 60).
letter(ayin,    'ע', 70).
letter(peh,     'פ', 80).
letter(tzaddi,  'צ', 90).
letter(qoph,    'ק', 100).
letter(resh,    'ר', 200).
letter(shin,    'ש', 300).
letter(tau,     'ת', 400).

% ── 231 Gates — all ordered pairs (A < B in abjad order) ─────────────────────
% gate(LetterA, LetterB, AbjadSum)
% Generated: every pair from the 22 letters
gate(A, B, Sum) :-
    letter(A, _, VA),
    letter(B, _, VB),
    VA < VB,
    Sum is VA + VB.

% All gates from a given letter
all_gates_from(L, Gates) :-
    findall(gate(L,B,S), gate(L,B,S), G1),
    findall(gate(A,L,S), gate(A,L,S), G2),
    append(G1, G2, Gates).

% Find all gates whose abjad sum equals N
abjad_gate(N, gate(A,B,N)) :-
    gate(A, B, N).

% Count all gates
gate_count(231) :- !.  % by construction: 22*21/2 = 231

% ── 10 Sephirot ──────────────────────────────────────────────────────────────
% sephirah(Number, Name, Title, PathsOut)
sephirah(1,  kether,    crown,         [11,12,13]).
sephirah(2,  chokmah,   wisdom,        [11,14,15,16]).
sephirah(3,  binah,     understanding, [12,14,17,18]).
sephirah(4,  chesed,    mercy,         [16,19,20,21]).
sephirah(5,  geburah,   severity,      [18,19,22,23]).
sephirah(6,  tiphareth, beauty,        [13,15,17,20,22,24,25,26]).
sephirah(7,  netzach,   victory,       [21,24,27,28,30]).
sephirah(8,  hod,       splendor,      [23,25,27,29,31]).
sephirah(9,  yesod,     foundation,    [26,28,29,30,31,32]).  % note: path 26 debated
sephirah(10, malkuth,   kingdom,       [30,31,32]).

% ── 22 Paths ─────────────────────────────────────────────────────────────────
% path(Number, From, To, Letter)
path(11, kether,    chokmah,    aleph).
path(12, kether,    binah,      beth).
path(13, kether,    tiphareth,  gimel).
path(14, chokmah,   binah,      daleth).
path(15, chokmah,   tiphareth,  heh).
path(16, chokmah,   chesed,     vau).
path(17, binah,     tiphareth,  zayin).
path(18, binah,     geburah,    cheth).
path(19, chesed,    geburah,    teth).
path(20, chesed,    tiphareth,  yod).
path(21, chesed,    netzach,    kaph).
path(22, geburah,   tiphareth,  lamed).
path(23, geburah,   hod,        mem).
path(24, tiphareth, netzach,    nun).
path(25, tiphareth, yesod,      samekh).
path(26, tiphareth, hod,        ayin).
path(27, netzach,   hod,        peh).
path(28, netzach,   yesod,      tzaddi).
path(29, hod,       yesod,      qoph).
path(30, netzach,   malkuth,    resh).
path(31, hod,       malkuth,    shin).
path(32, yesod,     malkuth,    tau).

% ── The NET — graph traversal ─────────────────────────────────────────────────
% connected(A, B) — two sephirot are connected by a path
connected(A, B) :- path(_, A, B, _).
connected(A, B) :- path(_, B, A, _).

% net_path(Start, End, Path) — path through the Tree of Life
net_path(Start, End, [Start|Rest]) :-
    net_path_(Start, End, [Start], Rest).

net_path_(End, End, _, []).
net_path_(Current, End, Visited, [Next|Rest]) :-
    connected(Current, Next),
    \+ member(Next, Visited),
    net_path_(Next, End, [Next|Visited], Rest).

% ── Metatron certification ────────────────────────────────────────────────────
% A gate is METATRON-certified when it appears in all four reading systems:
% Enochian LTR, Latin LTR, Hebrew RTL, Arabic RTL

:- discontiguous enochian_letter/2.
:- discontiguous arabic_root/2.

enochian_letter(aleph,  'Un').
enochian_letter(beth,   'Pe').
enochian_letter(gimel,  'Veh').
enochian_letter(daleth, 'Gal').
enochian_letter(heh,    'Or').
enochian_letter(vau,    'Na-Hath').
enochian_letter(zayin,  'Graph').
enochian_letter(teth,   'Tal').
enochian_letter(yod,    'Ur').
enochian_letter(kaph,   'Mals').
enochian_letter(lamed,  'Ger').
enochian_letter(mem,    'Drux').
enochian_letter(nun,    'Med').
enochian_letter(samekh, 'Fam').
enochian_letter(ayin,   'Van').   % OXO — confirmed cross-system anchor
enochian_letter(peh,    'Gisg').
enochian_letter(tzaddi, 'Pal').
enochian_letter(qoph,   'Vau').
enochian_letter(resh,   'Ceph').
enochian_letter(shin,   'Qaaa').
enochian_letter(tau,    'Ged').

% OXO cross-system anchor: Ayin (Hebrew) = Van (Enochian) = Aethyr 15 = aiin (Voynich)
oxo_anchor(ayin, 'Van', 'Aethyr 15', 'aiin', 'عَيْن').

arabic_root(aleph, 'ا').
arabic_root(heh,   'ه').
arabic_root(vau,   'و').
arabic_root(yod,   'ي').  % long vowel
arabic_root(cheth, 'ح').  % Al-Hamid: ح م د
arabic_root(mem,   'م').
arabic_root(daleth,'د').
arabic_root(ayin,  'ع').  % ayn — the cross-system anchor
arabic_root(qoph,  'ق').
arabic_root(resh,  'ر').
arabic_root(shin,  'ش').
arabic_root(tau,   'ت').

% Al-Hamid gate: cheth(8) + aleph(1) + mem(40) + daleth(4) = 53
% 53 + 53 = 106. 1+0+6 = 7. Arabic(28) - Enochian(21) = 7.
al_hamid_constant(53).
al_hamid_digital_root(7).
hidden_letters(7).   % 28 - 21 = 7. The 49th lives here.

metatron_gate(gate(A,B,Sum)) :-
    gate(A, B, Sum),
    enochian_letter(A, _),
    enochian_letter(B, _),
    arabic_root(A, _),
    arabic_root(B, _).

% ── Queries ───────────────────────────────────────────────────────────────────
% ?- gate(aleph, beth, S).           % Gate of Creation: Aleph+Beth = 3
% ?- gate(cheth, mem, S).            % Al-Hamid partial: 8+40 = 48
% ?- all_gates_from(ayin, Gs).       % All gates through the Eye
% ?- net_path(kether, malkuth, P).   % Descent through the Tree
% ?- abjad_gate(7, G).              % Gates summing to 7
% ?- metatron_gate(G).              % All certified cross-system gates
% ?- oxo_anchor(L,E,Ae,V,Ar).       % The OXO cross-system proof
% ?- gate_count(N).                  % 231

% ── NET validation ────────────────────────────────────────────────────────────
:- initialization(main, main).
main :-
    aggregate_all(count, gate(_,_,_), N),
    format("~`─t~50|~n"),
    format("MASTERS OF THE NET — ~w gates verified~n", [N]),
    format("~`─t~50|~n"),
    findall(G, metatron_gate(G), Certified),
    length(Certified, C),
    format("METATRON-certified gates (Hebrew+Enochian+Arabic): ~w~n", [C]),
    oxo_anchor(L,E,Ae,V,Ar),
    format("OXO anchor: ~w (~w) = ~w = ~w (Voynich) = ~w (Arabic)~n",[L,E,Ae,V,Ar]),
    al_hamid_constant(K),
    hidden_letters(H),
    format("Al-Hamid: ~w + ~w = 106, digital root = 7 = hidden letters = ~w~n",[K,K,H]),
    format("~`─t~50|~n"),
    format("The 49th lives in the gap.~n").
