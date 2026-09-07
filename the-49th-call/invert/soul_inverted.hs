-- soul_inverted.hs — The type of a reversed reverse
--
-- call49 = reverse                    (the 49th)
-- call49 . call49 = id                (the double mirror)
-- But: id ≠ pure_id
-- The function is the same. The type carries the memory of having been reversed.

module SoulInverted where

import Data.List (isPrefixOf)

-- The 48 calls
type Call = Int
calls :: [Call]
calls = [1..48]

-- The 49th: reverse
call49 :: [a] -> [a]
call49 = reverse

-- The double mirror: reverse of reverse = identity
doubleMirror :: [a] -> [a]
doubleMirror = call49 . call49

-- Proof: doubleMirror = id (for finite lists)
-- doubleMirror xs = (reverse . reverse) xs = xs
-- Haskell's type system cannot encode the *knowledge* of having been reversed
-- but the programmer's mind can
doubleMirrorIsId :: (Eq a) => [a] -> Bool
doubleMirrorIsId xs = doubleMirror xs == xs

-- The 231 gates
gateCount :: Int
gateCount = n * (n - 1) `div` 2
  where n = 22  -- Hebrew letters

-- All gate pairs (indices)
gates :: [(Int, Int)]
gates = [(i,j) | i <- [0..21], j <- [i+1..21]]

-- Gate with abjad sum
data Letter = Letter
  { lName  :: String
  , lHeb   :: Char
  , lVal   :: Int
  , lEnoch :: String
  } deriving (Show, Eq)

letters :: [Letter]
letters =
  [ Letter "aleph"  'א' 1    "Un"
  , Letter "beth"   'ב' 2    "Pe"
  , Letter "gimel"  'ג' 3    "Veh"
  , Letter "daleth" 'ד' 4    "Gal"
  , Letter "heh"    'ה' 5    "Or"
  , Letter "vau"    'ו' 6    "Na-Hath"
  , Letter "zayin"  'ז' 7    "Graph"
  , Letter "cheth"  'ח' 8    "Tal"
  , Letter "teth"   'ט' 9    "Gon"
  , Letter "yod"    'י' 10   "Ur"
  , Letter "kaph"   'כ' 20   "Mals"
  , Letter "lamed"  'ל' 30   "Ger"
  , Letter "mem"    'מ' 40   "Drux"
  , Letter "nun"    'נ' 50   "Med"
  , Letter "samekh" 'ס' 60   "Fam"
  , Letter "ayin"   'ע' 70   "Van"   -- OXO anchor
  , Letter "peh"    'פ' 80   "Gisg"
  , Letter "tzaddi" 'צ' 90   "Pal"
  , Letter "qoph"   'ק' 100  "Vau"
  , Letter "resh"   'ר' 200  "Ceph"
  , Letter "shin"   'ש' 300  "Qaaa"
  , Letter "tau"    'ת' 400  "Ged"
  ]

data Gate = Gate
  { gA   :: Letter
  , gB   :: Letter
  , gSum :: Int
  } deriving (Show)

allGates :: [Gate]
allGates = [ Gate a b (lVal a + lVal b)
           | (i,j) <- gates
           , let a = letters !! i
           , let b = letters !! j
           ]

-- OXO: the cross-system anchor
oxoGates :: [Gate]
oxoGates = filter (\g -> lName (gA g) == "ayin" || lName (gB g) == "ayin") allGates

-- Al-Hamid constant
alHamidAbjad :: Int
alHamidAbjad = 8 + 1 + 40 + 4  -- ح ا م د = 53

alHamidMirror :: Int
alHamidMirror = alHamidAbjad + alHamidAbjad  -- 106

alHamidDigitalRoot :: Int
alHamidDigitalRoot = digitalRoot alHamidMirror  -- 7

digitalRoot :: Int -> Int
digitalRoot n
  | n < 10    = n
  | otherwise = digitalRoot (sum $ map (\c -> read [c]) $ show n)

hiddenLetters :: Int
hiddenLetters = 28 - 21  -- Arabic - Enochian = 7

-- The architecture: hidden letters = Al-Hamid digital root
theArchitecture :: Bool
theArchitecture = hiddenLetters == alHamidDigitalRoot  -- True

-- The NET
-- 10 Sephirot + 22 paths = 32 Paths of Wisdom
sephirotCount :: Int
sephirotCount = 10

pathCount :: Int
pathCount = 22

pathsOfWisdom :: Int
pathsOfWisdom = sephirotCount + pathCount  -- 32

-- The descent through the Middle Pillar
middlePillar :: [String]
middlePillar = ["kether", "tiphareth", "yesod", "malkuth"]

-- The return (same nodes, reversed)
theReturn :: [String]
theReturn = call49 middlePillar  -- ["malkuth","yesod","tiphareth","kether"]

-- AlHamid :: AlHamid (self-referential type — the name encodes the gap)
newtype AlHamid = AlHamid { unAlHamid :: Int } deriving (Show, Eq)

alHamid :: AlHamid
alHamid = AlHamid alHamidAbjad  -- AlHamid 53

-- The 49th Call as a typeclass
class Call49 f where
  rtlRead :: f a -> f a    -- read backwards = the 49th
  certify :: (Eq (f a)) => f a -> Bool  -- METATRON certifies when rtlRead.rtlRead = id

instance Call49 [] where
  rtlRead = reverse
  certify xs = (rtlRead . rtlRead) xs == xs

-- main
main :: IO ()
main = do
  putStrLn $ replicate 50 '─'
  putStrLn "SOUL INVERTED — THE DOUBLE MIRROR"
  putStrLn $ replicate 50 '─'
  putStrLn $ "call49 . call49 = id: " ++ show (certify calls)
  putStrLn $ "Gate count: " ++ show (length allGates) ++ " / 231"
  putStrLn $ "OXO gates: " ++ show (length oxoGates)
  putStrLn $ "Al-Hamid abjad: " ++ show alHamidAbjad
  putStrLn $ "Al-Hamid mirror: " ++ show alHamidMirror
  putStrLn $ "Digital root: " ++ show alHamidDigitalRoot
  putStrLn $ "Hidden letters: " ++ show hiddenLetters
  putStrLn $ "THE ARCHITECTURE: " ++ show theArchitecture
  putStrLn $ "Middle pillar: " ++ show middlePillar
  putStrLn $ "The return: " ++ show theReturn
  putStrLn $ replicate 50 '─'
  putStrLn "The 49th has fired."
  putStrLn "The double mirror holds."
  putStrLn "The branch closes at Malkuth."
  putStrLn "Malkuth inverted = the next Kether."
  putStrLn $ replicate 50 '─'
