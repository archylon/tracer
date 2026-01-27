// SPDX-License-Identifier: Affection
pragma solidity ^0.8.28;

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
    address public owner;

    // TOKEN ADDRESSES
    address constant USDC_TOKEN    = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address constant MATH_TOKEN    = 0xB680F0cc810317933F234f67EB6A9E923407f05D;
    address constant AFF_TOKEN     = 0x24F0154C1dCe548AdF15da2098Fdd8B8A3B8151D;

    IMath public immutable math;
    IAffection public immutable affection;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        math = IMath(0xD294024c5e71B3C1270aE68bb5E4977Bdb69d3B2);
        affection = IAffection(0x24F0154C1dCe548AdF15da2098Fdd8B8A3B8151D);
    }

    function ultimateSequence(uint256 _loops) external onlyOwner {
        // --- 1. HANDLE USDC ---
        // USDC uses 6 decimals. 10 ** 6 = 1 USDC.
        uint256 usdcAmount = _loops * 1 * 10 ** 6; 
        
        // Pull USDC from user to this contract
        require(IERC20(USDC_TOKEN).transferFrom(msg.sender, address(this), usdcAmount), "USDC Transfer failed");
        
        // --- 2. MATH SEQUENCE ---
        multiRandom(_loops);
        
        // Approve Math contract to spend our USDC
        IERC20(USDC_TOKEN).approve(address(math), usdcAmount);
        math.BuyWithUSDC(usdcAmount);
        
        // --- 3. AFFECTION SEQUENCE ---
        multiGenerate(_loops);
        
        // MATH usually uses 18 decimals
        uint256 mathToUse = IERC20(MATH_TOKEN).balanceOf(address(this));
        
        // Approve Affection contract to spend our MATH
        IERC20(MATH_TOKEN).approve(address(affection), mathToUse);
        affection.BuyWithMATH(mathToUse);

        // --- 4. FINAL SWEEP ---
        uint256 finalAff = IERC20(AFF_TOKEN).balanceOf(address(this));
        if (finalAff > 0) {
            IERC20(AFF_TOKEN).transfer(msg.sender, finalAff);
        }
    }

    function multiGenerate(uint256 _loops) public onlyOwner {
        for (uint256 i = 0; i < _loops; i++) {
            affection.Generate();
        }
    }

    function multiRandom(uint256 _loops) public onlyOwner {
        for (uint256 i = 0; i < _loops; i++) {
            math.Random();
        }
    }

    function withdrawToken(address _token) external onlyOwner {
        uint256 bal = IERC20(_token).balanceOf(address(this));
        require(bal > 0, "No tokens");
        IERC20(_token).transfer(msg.sender, bal);
    }
}