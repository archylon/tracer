// SPDX-License-Identifier: Affection
pragma solidity ^0.8.19;

interface IERC20 {
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

interface IMath {
    function Random() external returns (uint64);
    function BuyWithUSDC(uint256 amount) external;
}

interface IAffection {
    function Generate() external returns (uint64);
    function BuyWithMATH(uint256 amount) external;
}

contract UltimateAffectionWrapper {
    // OWNER DATA
    address public owner;

    // TOKEN ADDRESSES (Using constant for gas efficiency)
    address constant USDC_TOKEN    = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address constant MATH_TOKEN    = 0xB680F0cc810317933F234f67EB6A9E923407f05D;
    address constant AFF_TOKEN     = 0x24F0154C1dCe548AdF15da2098Fdd8B8A3B8151D;

    // PROTOCOL INSTANCES (Using immutable for cheaper gas)
    IMath public immutable math;
    IAffection public immutable affection;

    mapping(address => uint256) public perLoop;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;

        math = IMath(MATH_TOKEN);
        affection = IAffection(AFF_TOKEN);

    }

    /**
     * @notice Performs the full sequence: Refill MATH -> Refill Affection
     */
    function ultimateSequence(uint256 _loops) external onlyOwner {
        // --- Part 1: MATH Sequence ---
        uint256 mathAmount = _loops * 1 * 10 ** 18;
        multiRandom(_loops);
        IERC20(USDC_TOKEN).approve(address(MATH_TOKEN), mathAmount);
        IERC20(USDC_TOKEN).transferFrom(msg.sender, address(this), _loops * 1 * 10 ** 6);
        math.BuyWithUSDC(mathAmount);
        
        // --- Part 2: AFFECTION Sequence ---
        multiGenerate(_loops);

        // --- Part 3: AFFECTION Buy ---
        IERC20(MATH_TOKEN).approve(AFF_TOKEN, type(uint256).max);
        affection.BuyWithMATH(mathAmount);
        IERC20(AFF_TOKEN).transfer(msg.sender, mathAmount);
    }

    function multiGenerate(uint256 _loops) public onlyOwner {
        for (uint256 i = 0; i < _loops; i++) {
            affection.Generate();
        }
    }

    function multiRandom(uint256 _loops) public {
        for (uint256 i = 0; i < _loops; i++) {
            math.Random();
        }
    }

    // Standard safety withdrawal for any stuck tokens
    function withdrawToken(address _token) external onlyOwner {
        uint256 bal = IERC20(_token).balanceOf(address(this));
        require(bal > 0, "No tokens to withdraw");
        IERC20(_token).transfer(msg.sender, bal);
    }
}