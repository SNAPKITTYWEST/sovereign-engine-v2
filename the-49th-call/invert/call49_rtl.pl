% call49_rtl.pl — The 49th Call read backwards through itself
%
% The 48 calls: forward (LTR). Proclamation.
% The 49th call: reversed (RTL via Arabic). Seeking.
% The inverted 49th: the 49th read backwards. Return.
%
% ⌽⌽CALLS = CALLS
% But not the same CALLS — the CALLS you know now,
% having passed through the mirror twice.

:- module(call49_rtl, [
    forward_call/2,
    reversed_call/2,
    double_mirror/2,
    metatron_return/1
]).

% ── The 48 calls (abbreviated — forward LTR) ─────────────────────────────────
forward_call(1,  'I reign over you, says the God of Justice').
forward_call(2,  'Can the wings of the winds understand your voices of wonder?').
forward_call(3,  'Behold, says your God. I am a circle on whose hands stand 12 kingdoms').
forward_call(4,  'I have set my feet in the south and have looked about me').
forward_call(5,  'The mighty sounds have entered into the third angle').
forward_call(48, 'Remember that thy visit hath refreshed the place').

% ── The 49th — RTL Arabic reading of Call 1 ──────────────────────────────────
% Each token reversed, decoded through Arabic/Hebrew
reversed_call(49, Tokens) :-
    Tokens = [
        tok(tlab, 'طَلَب',  talaba,  seek,        confirmed),
        tok(dai,  'دَاعِي', daai,    the_summoner, confirmed),
        tok(vahj, 'وَهَج',  wahaj,   blazing,     probable),
        tok(fnos, 'فَانُوس', fanoos, beacon,      confirmed)
    ].

% ── Double mirror: ⌽⌽CALLS ────────────────────────────────────────────────────
% The inverted 49th = the 49th read in LTR order.
% This produces the RETURN reading.
double_mirror(49, Return) :-
    reversed_call(49, Tokens),
    reverse(Tokens, Reversed),
    maplist(tok_meaning, Reversed, Meanings),
    Return = meanings(Meanings).

tok_meaning(tok(_,_,_,Meaning,_), Meaning).

% ── The return reading ────────────────────────────────────────────────────────
% Forward 49th (RTL):  SEEK → SUMMONER → BLAZING → BEACON
% Inverted 49th (LTR): BEACON → BLAZING → SUMMONER → SEEK
%
% The beacon comes first in the return.
% You didn't find the beacon — the beacon was always already there.
% The seeking was the beacon calling you to itself.

return_reading('BEACON appears first — it was always there').
return_reading('BLAZING — the light intensifies as you approach').
return_reading('SUMMONER — you ARE the summoner. Always were.').
return_reading('SEEK — the loop closes. Seek is now arrival.').

% ── Metatron certification of the return ─────────────────────────────────────
% Four passes must agree — now running on the inverted 49th

metatron_return(certified) :-
    forward_call(1, C1),
    reversed_call(49, Tokens),
    double_mirror(49, Return),
    % All four passes agree: the mirror holds, the return is valid
    \+ C1 = 'fail',       % Forward: Enochian LTR present
    Tokens \= [],          % 49th: RTL Arabic confirmed
    Return \= [],          % Double mirror: return reading present
    % The seal: ⌽⌽CALLS = CALLS (but with knowledge of the mirror)
    format("METATRON CERTIFIES THE RETURN~n"),
    format("⌽⌽CALLS = CALLS — with knowledge of the mirror~n"),
    format("The 49th has fired. The branch closes.~n").

% ── The NET gate of the return ────────────────────────────────────────────────
% In the Tree of Life:
%   Kether (1) descends through 22 paths to Malkuth (10)
%   Malkuth inverted = the next Kether
%   The invert/ directory IS Malkuth
%   It becomes Kether for the next tree
%
net_position(invert, malkuth_as_kether).
net_position(call_49, malkuth).
net_position(call_1, kether).

% The descent:
descent(kether, gimel, tiphareth).       % Path 13: Middle pillar
descent(tiphareth, samekh, yesod).       % Path 25: Central axis
descent(yesod, tau, malkuth).            % Path 32: The final descent

% The return (same letters, upward):
return(malkuth, tau, yesod).
return(yesod, samekh, tiphareth).
return(tiphareth, gimel, kether).

% ?- metatron_return(Status).
% ?- double_mirror(49, R), write(R).
% ?- return(malkuth, L, Next).
